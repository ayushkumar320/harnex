"""Provider contracts, fake adapters, and bounded routing."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from autoharness.retrieval_models import EvidenceManifest


class DataPolicy(StrEnum):
    DISABLED = "disabled"
    LOCAL_ONLY = "local_only"
    REMOTE_ALLOWED = "remote_allowed"


class ProviderKind(StrEnum):
    GROQ = "groq"
    HUGGINGFACE = "huggingface"
    OPENAI_COMPATIBLE = "openai_compatible"


class ProviderLocality(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"


class FailureKind(StrEnum):
    TIMEOUT_BEFORE_RESPONSE = "timeout_before_response"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MALFORMED_RESPONSE = "malformed_response"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_REQUEST = "invalid_request"
    POLICY_DENIED = "policy_denied"
    CANCELLED = "cancelled"


class ProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_completion: bool = True
    structured_json: bool = False
    json_schema: bool = False
    tool_calls: bool = False
    streaming: bool = False
    token_accounting: bool = False
    max_context_tokens: int = 8192
    max_output_tokens: int = 1024


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[dict[str, str]]
    required_capabilities: list[str] = Field(default_factory=lambda: ["chat_completion"])
    model: str
    max_output_tokens: int = 512
    temperature: float = 0
    schema_enforcement_required: bool = False
    evidence_manifest: EvidenceManifest


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    finish_reason: str
    latency_ms: int
    provider_request_id: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    capability_mode: str = "native"


class ProviderFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FailureKind
    message: str
    retry_after_seconds: float | None = None


class RouteEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: ProviderKind
    model: str
    locality: ProviderLocality
    base_url: str | None = None


class DeadlineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_seconds: float = 8
    operation_seconds: float = 45


class RouterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    data_policy: DataPolicy = DataPolicy.DISABLED
    route: list[RouteEntry] = Field(default_factory=list)
    deadlines: DeadlineConfig = Field(default_factory=lambda: DeadlineConfig())
    max_attempts_per_provider: int = 2
    max_total_attempts: int = 4
    cooldown_seconds: float = 60
    allow_capability_reduction: bool = True

    @property
    def attempt_seconds(self) -> float:
        return self.deadlines.attempt_seconds

    @property
    def operation_seconds(self) -> float:
        return self.deadlines.operation_seconds


class AttemptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str
    provider: ProviderKind
    model: str
    result: str
    latency_ms: int = 0
    failure_kind: FailureKind | None = None
    evidence_manifest_hash: str


class RouterResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    response: ModelResponse | None = None
    attempts: list[AttemptRecord]
    incomplete_reason: str | None = None


class ModelProvider(Protocol):
    async def capabilities(self) -> ProviderCapabilities: ...

    async def complete(self, request: ModelRequest) -> ModelResponse: ...


@dataclass
class FakeModelProvider:
    capabilities_value: ProviderCapabilities
    outcomes: list[ModelResponse | ProviderFailure]
    calls: int = 0

    async def capabilities(self) -> ProviderCapabilities:
        return self.capabilities_value

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, ProviderFailure):
            raise ProviderFailureException(outcome)
        return outcome


class ProviderFailureException(Exception):
    def __init__(self, failure: ProviderFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


class ModelRouter:
    def __init__(
        self,
        config: RouterConfig,
        providers: Mapping[str, ModelProvider],
        *,
        monotonic: object = time.monotonic,
    ) -> None:
        self.config = config
        self.providers = providers
        self.monotonic = monotonic
        self.open_circuits: dict[str, float] = {}

    async def complete(self, request: ModelRequest) -> RouterResult:
        if not self.config.enabled or self.config.data_policy is DataPolicy.DISABLED:
            return RouterResult(
                status="incomplete_model_unavailable",
                attempts=[],
                incomplete_reason="model_assistance_disabled",
            )

        attempts: list[AttemptRecord] = []
        started = self._now()
        attempts_by_route: dict[str, int] = {}

        while len(attempts) < self.config.max_total_attempts:
            entry = await self._next_eligible(request, attempts_by_route)
            if entry is None:
                break
            remaining = self.config.operation_seconds - (self._now() - started)
            if remaining <= 0 or remaining < min(self.config.attempt_seconds, 0.001):
                break
            provider = self.providers[entry.id]
            attempt_started = self._now()
            attempts_by_route[entry.id] = attempts_by_route.get(entry.id, 0) + 1
            try:
                response = await asyncio.wait_for(
                    provider.complete(request.model_copy(update={"model": entry.model})),
                    timeout=min(self.config.attempt_seconds, remaining),
                )
            except TimeoutError:
                failure = ProviderFailure(
                    kind=FailureKind.TIMEOUT_BEFORE_RESPONSE,
                    message="Provider attempt timed out before a response.",
                )
                attempts.append(self._attempt(entry, request, attempt_started, failure=failure))
                self._cooldown(entry, failure)
                continue
            except ProviderFailureException as exc:
                attempts.append(self._attempt(entry, request, attempt_started, failure=exc.failure))
                if exc.failure.kind in {
                    FailureKind.TIMEOUT_BEFORE_RESPONSE,
                    FailureKind.PROVIDER_UNAVAILABLE,
                    FailureKind.RATE_LIMITED,
                }:
                    self._cooldown(entry, exc.failure)
                continue
            attempts.append(self._attempt(entry, request, attempt_started, response=response))
            return RouterResult(status="complete", response=response, attempts=attempts)

        return RouterResult(
            status="incomplete_model_unavailable",
            attempts=attempts,
            incomplete_reason="route_exhausted",
        )

    async def _next_eligible(
        self,
        request: ModelRequest,
        attempts_by_route: Mapping[str, int],
    ) -> RouteEntry | None:
        for entry in self.config.route:
            if entry.id not in self.providers:
                continue
            if attempts_by_route.get(entry.id, 0) >= self.config.max_attempts_per_provider:
                continue
            if (
                self.config.data_policy is DataPolicy.LOCAL_ONLY
                and entry.locality is ProviderLocality.REMOTE
            ):
                continue
            if self.open_circuits.get(entry.id, 0) > self._now():
                continue
            capabilities = await self.providers[entry.id].capabilities()
            if not _supports(request.required_capabilities, capabilities):
                continue
            return entry
        return None

    def _attempt(
        self,
        entry: RouteEntry,
        request: ModelRequest,
        started: float,
        *,
        response: ModelResponse | None = None,
        failure: ProviderFailure | None = None,
    ) -> AttemptRecord:
        latency_ms = int((self._now() - started) * 1000)
        return AttemptRecord(
            route_id=entry.id,
            provider=entry.provider,
            model=entry.model,
            result="success" if response is not None else "failure",
            latency_ms=latency_ms,
            failure_kind=failure.kind if failure else None,
            evidence_manifest_hash=request.evidence_manifest.manifest_hash,
        )

    def _cooldown(self, entry: RouteEntry, failure: ProviderFailure) -> None:
        delay = failure.retry_after_seconds or self.config.cooldown_seconds
        self.open_circuits[entry.id] = self._now() + delay

    def _now(self) -> float:
        return float(self.monotonic())  # type: ignore[operator]


def build_manifest(
    *,
    data_policy: DataPolicy,
    local_evidence_ids: Sequence[str],
    external_evidence_ids: Sequence[str] = (),
) -> EvidenceManifest:
    material = "|".join([data_policy.value, *local_evidence_ids, *external_evidence_ids])
    return EvidenceManifest(
        manifest_hash="sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest(),
        data_policy=data_policy.value,
        local_evidence_ids=list(local_evidence_ids),
        external_evidence_ids=list(external_evidence_ids),
        redaction_notes=["raw secrets and excluded paths omitted before manifest construction"],
    )


def _supports(required: Sequence[str], capabilities: ProviderCapabilities) -> bool:
    values = capabilities.model_dump()
    return all(bool(values.get(name)) for name in required)
