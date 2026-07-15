"""Provider contracts, fake adapters, and bounded routing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    @model_validator(mode="after")
    def validate_deadlines(self) -> DeadlineConfig:
        if self.attempt_seconds <= 0 or self.operation_seconds <= 0:
            raise ValueError("provider deadlines must be positive")
        if self.attempt_seconds > self.operation_seconds:
            raise ValueError("attempt deadline must fit inside operation deadline")
        return self


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

    @field_validator("max_attempts_per_provider", "max_total_attempts")
    @classmethod
    def positive_attempts(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("attempt limits must be positive")
        return value

    @field_validator("cooldown_seconds")
    @classmethod
    def non_negative_cooldown(cls, value: float) -> float:
        if value < 0:
            raise ValueError("cooldown must be non-negative")
        return value

    @model_validator(mode="after")
    def validate_route(self) -> RouterConfig:
        route_ids = [entry.id for entry in self.route]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("route ids must be unique")
        if self.enabled and self.data_policy is DataPolicy.DISABLED:
            raise ValueError(
                "enabled model assistance requires local_only or remote_allowed policy"
            )
        for entry in self.route:
            if entry.base_url and _looks_local_url(entry.base_url) != (
                entry.locality is ProviderLocality.LOCAL
            ):
                raise ValueError("route base_url locality must match the declared locality")
        return self

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
    skip_reason: str | None = None
    evidence_manifest_hash: str


class RouterResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    response: ModelResponse | None = None
    attempts: list[AttemptRecord]
    skipped: list[AttemptRecord] = Field(default_factory=list)
    incomplete_reason: str | None = None


class CircuitRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str
    failure_kind: FailureKind
    consecutive_transient_failures: int
    cooldown_until: float


class FileCircuitStore:
    """Bounded redaction-safe provider health state."""

    def __init__(self, path: Path, *, max_records: int = 64) -> None:
        self.path = path
        self.max_records = max_records

    def load(self) -> dict[str, CircuitRecord]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        records = payload.get("records", {})
        if not isinstance(records, dict):
            return {}
        return {
            route_id: CircuitRecord.model_validate(record)
            for route_id, record in records.items()
            if isinstance(record, dict)
        }

    def save(self, records: Mapping[str, CircuitRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        bounded = dict(sorted(records.items())[: self.max_records])
        payload = {
            "schema_version": "1.0",
            "records": {
                route_id: record.model_dump(mode="json") for route_id, record in bounded.items()
            },
        }
        self.path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )


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
        circuit_store: FileCircuitStore | None = None,
    ) -> None:
        self.config = config
        self.providers = providers
        self.monotonic = monotonic
        self.circuit_store = circuit_store
        self.circuits: dict[str, CircuitRecord] = (
            circuit_store.load() if circuit_store is not None else {}
        )
        self.open_circuits: dict[str, float] = {
            route_id: record.cooldown_until for route_id, record in self.circuits.items()
        }

    async def complete(self, request: ModelRequest) -> RouterResult:
        if not self.config.enabled or self.config.data_policy is DataPolicy.DISABLED:
            return RouterResult(
                status="incomplete_model_unavailable",
                attempts=[],
                skipped=[],
                incomplete_reason="model_assistance_disabled",
            )

        attempts: list[AttemptRecord] = []
        skipped: list[AttemptRecord] = []
        started = self._now()
        attempts_by_route: dict[str, int] = {}

        while len(attempts) < self.config.max_total_attempts:
            entry = await self._next_eligible(request, attempts_by_route, skipped)
            if entry is None:
                break
            remaining = self.config.operation_seconds - (self._now() - started)
            if remaining <= 0 or remaining < min(self.config.attempt_seconds, 0.001):
                break
            provider = self.providers[entry.id]
            attempt_started = self._now()
            attempts_by_route[entry.id] = attempts_by_route.get(entry.id, 0) + 1
            try:
                routed_request = request.model_copy(update={"model": entry.model})
                response = await asyncio.wait_for(
                    provider.complete(routed_request),
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
            return RouterResult(
                status="complete",
                response=response,
                attempts=attempts,
                skipped=skipped,
            )

        return RouterResult(
            status="incomplete_model_unavailable",
            attempts=attempts,
            skipped=skipped,
            incomplete_reason="route_exhausted",
        )

    async def _next_eligible(
        self,
        request: ModelRequest,
        attempts_by_route: Mapping[str, int],
        skipped: list[AttemptRecord],
    ) -> RouteEntry | None:
        for entry in self.config.route:
            if entry.id not in self.providers:
                skipped.append(self._skip(entry, request, "provider_not_registered"))
                continue
            if attempts_by_route.get(entry.id, 0) >= self.config.max_attempts_per_provider:
                skipped.append(self._skip(entry, request, "max_attempts_reached"))
                continue
            if (
                self.config.data_policy is DataPolicy.LOCAL_ONLY
                and entry.locality is ProviderLocality.REMOTE
            ):
                skipped.append(self._skip(entry, request, "local_only_policy"))
                continue
            if self.open_circuits.get(entry.id, 0) > self._now():
                skipped.append(self._skip(entry, request, "circuit_open"))
                continue
            capabilities = await self.providers[entry.id].capabilities()
            supported, reason = _supports_request(request, capabilities, self.config)
            if not supported:
                skipped.append(self._skip(entry, request, reason))
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

    def _skip(self, entry: RouteEntry, request: ModelRequest, reason: str) -> AttemptRecord:
        return AttemptRecord(
            route_id=entry.id,
            provider=entry.provider,
            model=entry.model,
            result="skipped",
            skip_reason=reason,
            evidence_manifest_hash=request.evidence_manifest.manifest_hash,
        )

    def _cooldown(self, entry: RouteEntry, failure: ProviderFailure) -> None:
        delay = failure.retry_after_seconds or self.config.cooldown_seconds
        prior = self.circuits.get(entry.id)
        self.circuits[entry.id] = CircuitRecord(
            route_id=entry.id,
            failure_kind=failure.kind,
            consecutive_transient_failures=(
                (prior.consecutive_transient_failures + 1) if prior is not None else 1
            ),
            cooldown_until=self._now() + delay,
        )
        self.open_circuits[entry.id] = self.circuits[entry.id].cooldown_until
        if self.circuit_store is not None:
            self.circuit_store.save(self.circuits)

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


def _supports_request(
    request: ModelRequest,
    capabilities: ProviderCapabilities,
    config: RouterConfig,
) -> tuple[bool, str]:
    values = capabilities.model_dump()
    missing = [name for name in request.required_capabilities if not bool(values.get(name))]
    if not missing:
        return True, ""
    if (
        missing == ["json_schema"]
        and not request.schema_enforcement_required
        and config.allow_capability_reduction
        and capabilities.structured_json
    ):
        return True, "capability_reduction_json_schema_local_validation"
    return False, "unsupported_capability:" + ",".join(missing)


def _looks_local_url(url: str) -> bool:
    lowered = url.lower()
    return (
        lowered.startswith("http://127.0.0.1")
        or lowered.startswith("http://localhost")
        or lowered.startswith("http://[::1]")
    )
