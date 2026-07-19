import json

import pytest

from autoharness.external_evidence import (
    EvidenceExtractRequest,
    EvidenceSearchRequest,
    FakeExternalEvidenceProvider,
    FileExternalEvidenceCache,
    TavilyExternalEvidenceProvider,
    estimate_search_cost,
    external_evidence,
    validate_official_domain,
    validate_query_privacy,
)


def test_external_query_privacy_rejects_secret_like_material() -> None:
    with pytest.raises(ValueError):
        validate_query_privacy("openai OPENAI_API_KEY=sk-secret")


def test_external_budget_and_domain_policy() -> None:
    request = EvidenceSearchRequest(
        query="openai chat completions create",
        include_domains=["platform.openai.com"],
        credits_remaining=0,
    )

    assert estimate_search_cost(request).allowed is False
    assert validate_official_domain("https://platform.openai.com/docs", ["platform.openai.com"])
    with pytest.raises(ValueError):
        validate_official_domain("https://example.com/docs", ["platform.openai.com"])


@pytest.mark.asyncio
async def test_fake_external_provider_filters_to_official_domains() -> None:
    evidence = external_evidence(
        url="https://platform.openai.com/docs",
        title="OpenAI Docs",
        text="Official docs",
        query="openai docs",
        allowed_domains=["platform.openai.com"],
    )
    provider = FakeExternalEvidenceProvider([evidence])
    results = await provider.search(
        EvidenceSearchRequest(
            query="openai docs",
            include_domains=["platform.openai.com"],
            credits_remaining=1,
        )
    )

    assert provider.calls == 1
    assert results == [evidence]


class TavilyClient:
    def __init__(self) -> None:
        self.search_kwargs = None
        self.extract_kwargs = None

    def search(self, **kwargs):
        self.search_kwargs = kwargs
        return {
            "results": [
                {
                    "url": "https://platform.openai.com/docs",
                    "title": "OpenAI Docs",
                    "content": "Official OpenAI API docs.",
                    "score": 0.9,
                },
                {
                    "url": "https://example.com/blog",
                    "title": "Blog",
                    "content": "Rejected domain.",
                    "score": 0.8,
                },
            ]
        }

    def extract(self, **kwargs):
        self.extract_kwargs = kwargs
        return {
            "results": [
                {
                    "url": "https://platform.openai.com/docs",
                    "title": "OpenAI Docs",
                    "raw_content": "Extracted official content.",
                }
            ]
        }


@pytest.mark.asyncio
async def test_tavily_adapter_search_uses_privacy_and_official_domain_policy() -> None:
    client = TavilyClient()
    provider = TavilyExternalEvidenceProvider(client=client)

    results = await provider.search(
        EvidenceSearchRequest(
            query="openai responses api",
            include_domains=["platform.openai.com"],
            credits_remaining=1,
        )
    )

    assert client.search_kwargs["include_answer"] is False
    assert client.search_kwargs["search_depth"] == "basic"
    assert [item.domain for item in results] == ["platform.openai.com"]
    assert results[0].relevance_score == 0.9


@pytest.mark.asyncio
async def test_tavily_adapter_extract_batches_allowed_urls() -> None:
    client = TavilyClient()
    provider = TavilyExternalEvidenceProvider(client=client)

    results = await provider.extract(
        EvidenceExtractRequest(
            urls=["https://platform.openai.com/docs"],
            query="openai docs",
            include_domains=["platform.openai.com"],
            credits_remaining=1,
        )
    )

    assert client.extract_kwargs["urls"] == ["https://platform.openai.com/docs"]
    assert results[0].text == "Extracted official content."


def test_file_external_evidence_cache_round_trips_and_expires(tmp_path) -> None:
    request = EvidenceSearchRequest(
        query="openai docs",
        include_domains=["platform.openai.com"],
        credits_remaining=1,
    )
    evidence = [
        external_evidence(
            url="https://platform.openai.com/docs",
            title="OpenAI Docs",
            text="Official docs",
            query="openai docs",
            allowed_domains=["platform.openai.com"],
        )
    ]
    cache = FileExternalEvidenceCache(tmp_path / "cache", ttl_days=14)
    expired_cache = FileExternalEvidenceCache(tmp_path / "cache", ttl_days=-1)

    cache.put(request, evidence)

    assert cache.get(request) == evidence
    assert expired_cache.get(request) is None


def test_file_external_evidence_cache_rejects_tampered_domain_and_content(tmp_path) -> None:
    request = EvidenceSearchRequest(
        query="openai docs",
        include_domains=["platform.openai.com"],
        credits_remaining=1,
    )
    evidence = [
        external_evidence(
            url="https://platform.openai.com/docs",
            title="OpenAI Docs",
            text="Official docs",
            query=request.query,
            allowed_domains=request.include_domains,
        )
    ]
    cache = FileExternalEvidenceCache(tmp_path / "cache", ttl_days=14)
    cache.put(request, evidence)
    cache_path = cache._path(request)
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["evidence"][0]["final_url"] = "https://example.com/injected"
    payload["evidence"][0]["text"] = "tampered content"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    assert cache.get(request) is None
