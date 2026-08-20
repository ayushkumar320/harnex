"""External evidence privacy, budget, cache, and fake provider scaffolding."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentharness.retrieval_models import ExternalEvidence

PRIVATE_QUERY_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9_-]+"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*="),
    re.compile(r"(?i)(internal|localhost|127\.0\.0\.1|corp\.|private)"),
)

OFFICIAL_DOMAINS_BY_PACKAGE = {
    "groq": ["console.groq.com"],
    "huggingface": ["huggingface.co"],
    "langchain": ["python.langchain.com"],
    "langgraph": ["langchain-ai.github.io"],
    "openai": ["platform.openai.com"],
    "tavily": ["docs.tavily.com"],
}


class EvidenceSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    include_domains: list[str]
    max_results: int = 5
    credits_remaining: int = 3


class EvidenceExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[str]
    query: str
    include_domains: list[str]
    credits_remaining: int = 3


class CreditEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimated_credits: int
    allowed: bool
    reason: str | None = None


class ExternalEvidenceCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: bool = True
    extract: bool = True
    max_results: int = 5


class WebEvidenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    provider: str = "tavily"
    official_domains_only: bool = True
    search_depth: str = "basic"
    include_answer: bool = False
    max_credits_per_command: int = 3
    cache_ttl_days: int = 14
    max_results: int = 5
    max_extract_urls: int = 5


class ExternalEvidenceProvider(Protocol):
    def capabilities(self) -> ExternalEvidenceCapabilities: ...

    def estimate_cost(self, request: EvidenceSearchRequest) -> CreditEstimate: ...

    async def search(self, request: EvidenceSearchRequest) -> list[ExternalEvidence]: ...

    async def extract(self, request: EvidenceExtractRequest) -> list[ExternalEvidence]: ...


class TavilyClient(Protocol):
    def search(self, **kwargs: object) -> object: ...

    def extract(self, **kwargs: object) -> object: ...


@dataclass
class FakeExternalEvidenceProvider:
    results: list[ExternalEvidence]
    calls: int = 0

    def capabilities(self) -> ExternalEvidenceCapabilities:
        return ExternalEvidenceCapabilities()

    def estimate_cost(self, request: EvidenceSearchRequest) -> CreditEstimate:
        return estimate_search_cost(request)

    async def search(self, request: EvidenceSearchRequest) -> list[ExternalEvidence]:
        self.calls += 1
        validate_query_privacy(request.query)
        estimate = estimate_search_cost(request)
        if not estimate.allowed:
            return []
        allowed_domains = set(request.include_domains)
        filtered = [item for item in self.results if item.domain in allowed_domains]
        return filtered[: request.max_results]

    async def extract(self, request: EvidenceExtractRequest) -> list[ExternalEvidence]:
        self.calls += 1
        validate_query_privacy(request.query)
        if request.credits_remaining <= 0:
            return []
        allowed_domains = set(request.include_domains)
        return [
            item
            for item in self.results
            if item.final_url in request.urls and item.domain in allowed_domains
        ]


class TavilyExternalEvidenceProvider:
    """Tavily Search/Extract adapter with injectable client for contract tests."""

    def __init__(self, *, client: TavilyClient) -> None:
        self.client = client

    def capabilities(self) -> ExternalEvidenceCapabilities:
        return ExternalEvidenceCapabilities()

    def estimate_cost(self, request: EvidenceSearchRequest) -> CreditEstimate:
        return estimate_search_cost(request)

    async def search(self, request: EvidenceSearchRequest) -> list[ExternalEvidence]:
        validate_query_privacy(request.query)
        estimate = estimate_search_cost(request)
        if not estimate.allowed:
            return []
        response = self.client.search(
            query=request.query,
            search_depth="basic",
            include_answer=False,
            include_domains=request.include_domains,
            max_results=request.max_results,
        )
        return _normalize_search_response(response, request)

    async def extract(self, request: EvidenceExtractRequest) -> list[ExternalEvidence]:
        validate_query_privacy(request.query)
        if request.credits_remaining <= 0:
            return []
        for url in request.urls:
            validate_official_domain(url, request.include_domains)
        response = self.client.extract(urls=request.urls)
        return _normalize_extract_response(response, request)


def build_tavily_provider_from_env() -> TavilyExternalEvidenceProvider | None:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return None
    from tavily import TavilyClient as RealTavilyClient  # type: ignore[import-untyped]

    return TavilyExternalEvidenceProvider(client=RealTavilyClient(api_key=api_key))


class ExternalEvidenceCache(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: dict[str, list[ExternalEvidence]] = Field(default_factory=dict)

    def get(self, request: EvidenceSearchRequest) -> list[ExternalEvidence] | None:
        return self.entries.get(search_cache_key(request))

    def put(self, request: EvidenceSearchRequest, evidence: list[ExternalEvidence]) -> None:
        self.entries[search_cache_key(request)] = evidence


class FileExternalEvidenceCache:
    def __init__(self, root: Path, *, ttl_days: int = 14) -> None:
        self.root = root
        self.ttl = timedelta(days=ttl_days)

    def get(self, request: EvidenceSearchRequest) -> list[ExternalEvidence] | None:
        path = self._path(request)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != "1.0":
                return None
            if payload.get("cache_key") != search_cache_key(request):
                return None
            created_at = datetime.fromisoformat(payload["created_at"])
            if created_at.tzinfo is None or datetime.now(UTC) - created_at > self.ttl:
                return None
            evidence = [ExternalEvidence.model_validate(item) for item in payload["evidence"]]
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ValidationError,
        ):
            return None
        if not all(_cached_evidence_matches(item, request) for item in evidence):
            return None
        return evidence

    def put(self, request: EvidenceSearchRequest, evidence: list[ExternalEvidence]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "cache_key": search_cache_key(request),
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        self._path(request).write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    def _path(self, request: EvidenceSearchRequest) -> Path:
        filename = search_cache_key(request).removeprefix("sha256:") + ".json"
        return self.root / filename


def default_external_evidence_cache_root() -> Path:
    configured = os.environ.get("AGENTHARNESS_CACHE_DIR")
    if configured:
        return Path(configured).expanduser() / "external-evidence"
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / "agentharness" / "external-evidence"


def _cached_evidence_matches(
    evidence: ExternalEvidence,
    request: EvidenceSearchRequest,
) -> bool:
    expected_query_hash = "sha256:" + hashlib.sha256(request.query.encode("utf-8")).hexdigest()
    expected_content_hash = "sha256:" + hashlib.sha256(evidence.text.encode("utf-8")).hexdigest()
    try:
        canonical_domain = validate_official_domain(evidence.canonical_url, request.include_domains)
        final_domain = validate_official_domain(evidence.final_url, request.include_domains)
    except ValueError:
        return False
    return (
        evidence.domain == final_domain
        and canonical_domain == final_domain
        and evidence.query_hash == expected_query_hash
        and evidence.content_hash == expected_content_hash
    )


async def collect_external_evidence(
    *,
    local_texts: list[str],
    config: WebEvidenceConfig,
    provider: ExternalEvidenceProvider | None,
    cache: FileExternalEvidenceCache | None,
) -> tuple[list[ExternalEvidence], str | None]:
    """Collect bounded official external evidence for public package names only."""

    if not config.enabled:
        return [], "web_evidence_disabled"
    if provider is None:
        return [], "web_evidence_unavailable"

    plans = plan_public_queries(local_texts, max_queries=config.max_credits_per_command)
    if not plans:
        return [], "no_public_web_queries"

    credits_remaining = config.max_credits_per_command
    collected: list[ExternalEvidence] = []
    seen_ids: set[str] = set()
    for query, domains in plans:
        request = EvidenceSearchRequest(
            query=query,
            include_domains=domains,
            max_results=config.max_results,
            credits_remaining=credits_remaining,
        )
        cached = cache.get(request) if cache is not None else None
        if cached is not None:
            for item in cached:
                if item.id not in seen_ids:
                    collected.append(item)
                    seen_ids.add(item.id)
            continue
        estimate = provider.estimate_cost(request)
        if not estimate.allowed or estimate.estimated_credits > credits_remaining:
            return collected, estimate.reason or "budget_exhausted"
        fresh = await provider.search(request)
        credits_used = max(estimate.estimated_credits, sum(item.credits_used for item in fresh))
        credits_remaining -= credits_used
        if cache is not None:
            cache.put(request, fresh)
        for item in fresh:
            if item.id not in seen_ids:
                collected.append(item)
                seen_ids.add(item.id)
        if credits_remaining <= 0:
            break
    return collected, None if collected else "external_evidence_empty"


def plan_public_queries(local_texts: list[str], *, max_queries: int) -> list[tuple[str, list[str]]]:
    text = "\n".join(local_texts).lower()
    plans: list[tuple[str, list[str]]] = []
    for package, domains in sorted(OFFICIAL_DOMAINS_BY_PACKAGE.items()):
        if package in text:
            plans.append((f"{package} official documentation agent reliability", domains))
        if len(plans) >= max_queries:
            break
    return plans


def estimate_search_cost(request: EvidenceSearchRequest) -> CreditEstimate:
    if request.credits_remaining <= 0:
        return CreditEstimate(estimated_credits=1, allowed=False, reason="budget_exhausted")
    if not request.include_domains:
        return CreditEstimate(estimated_credits=1, allowed=False, reason="missing_official_domains")
    return CreditEstimate(estimated_credits=1, allowed=True)


def validate_query_privacy(query: str) -> None:
    for pattern in PRIVATE_QUERY_PATTERNS:
        if pattern.search(query):
            raise ValueError("external evidence query contains private or secret-like material")


def validate_official_domain(url: str, allowed_domains: list[str]) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("unsupported URL scheme")
    domain = parsed.netloc.lower()
    if domain not in set(allowed_domains):
        raise ValueError("external evidence domain is not approved")
    return domain


def search_cache_key(request: EvidenceSearchRequest) -> str:
    material = "|".join([request.query, *sorted(request.include_domains), str(request.max_results)])
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def external_evidence(
    *,
    url: str,
    title: str,
    text: str,
    query: str,
    allowed_domains: list[str],
    trust_label: Literal["official", "maintainer", "unverified"] = "official",
) -> ExternalEvidence:
    domain = validate_official_domain(url, allowed_domains)
    query_hash = "sha256:" + hashlib.sha256(query.encode("utf-8")).hexdigest()
    content_hash = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    return ExternalEvidence(
        id="external:" + content_hash.removeprefix("sha256:")[:16],
        canonical_url=url,
        final_url=url,
        title=title,
        domain=domain,
        content_hash=content_hash,
        text=text,
        query_hash=query_hash,
        relevance_score=1,
        credits_used=1,
        trust_label=trust_label,
    )


def _normalize_search_response(
    response: object,
    request: EvidenceSearchRequest,
) -> list[ExternalEvidence]:
    results = _response_results(response)
    evidence = []
    for item in results[: request.max_results]:
        url = str(_get(item, "url") or "")
        title = str(_get(item, "title") or url)
        text = str(_get(item, "content") or _get(item, "snippet") or "")
        score = _float_value(_get(item, "score"))
        if not url or not text:
            continue
        try:
            accepted = external_evidence(
                url=url,
                title=title,
                text=text,
                query=request.query,
                allowed_domains=request.include_domains,
            )
        except ValueError:
            continue
        evidence.append(accepted.model_copy(update={"relevance_score": score}))
    return evidence


def _normalize_extract_response(
    response: object,
    request: EvidenceExtractRequest,
) -> list[ExternalEvidence]:
    results = _response_results(response)
    evidence = []
    for item in results:
        url = str(_get(item, "url") or _get(item, "raw_url") or "")
        title = str(_get(item, "title") or url)
        text = str(_get(item, "raw_content") or _get(item, "content") or "")
        if not url or not text:
            continue
        try:
            evidence.append(
                external_evidence(
                    url=url,
                    title=title,
                    text=text,
                    query=request.query,
                    allowed_domains=request.include_domains,
                )
            )
        except ValueError:
            continue
    return evidence


def _response_results(response: object) -> list[object]:
    results = _get(response, "results")
    if isinstance(results, list):
        return results
    if isinstance(response, list):
        return response
    return []


def _get(obj: object, name: str) -> object | None:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0
    return 0
