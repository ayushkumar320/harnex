"""Runtime reliability primitives for generated harnesses."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

RUNTIME_SCHEMA_VERSION = "1.0"
MAX_EVENT_FIELD_CHARS = 512

_SECRET_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|credential|env|header|password|prompt|raw|secret|token)"
)
_SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(sk-[A-Za-z0-9_-]{8,}|api[_-]?key|authorization|credential|password|secret|token)"
)


class RuntimeEventType(StrEnum):
    RUN_STARTED = "run_started"
    MODEL_CALL_STARTED = "model_call_started"
    MODEL_CALL_FINISHED = "model_call_finished"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_FINISHED = "tool_call_finished"
    RETRY_SCHEDULED = "retry_scheduled"
    POLICY_BLOCK = "policy_block"
    RUN_FINISHED = "run_finished"


class RuntimeStatus(StrEnum):
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    RETRY_EXHAUSTED = "retry_exhausted"
    COMMIT_STATUS_UNKNOWN = "commit_status_unknown"
    POLICY_BLOCKED = "policy_blocked"


class RuntimeFailureKind(StrEnum):
    TIMEOUT_BEFORE_RESPONSE = "timeout_before_response"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MALFORMED_STRUCTURED_OUTPUT = "malformed_structured_output"
    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_REQUEST = "invalid_request"
    POLICY_DENIAL = "policy_denial"
    TOOL_FAILURE = "tool_failure"
    UNKNOWN_COMMIT_STATE = "unknown_commit_state"
    CANCELLED = "cancelled"


class SideEffectClassification(StrEnum):
    READ_ONLY = "read_only"
    IDEMPOTENT = "idempotent"
    TRANSACTIONAL = "transactional"
    NON_IDEMPOTENT = "non_idempotent"
    UNKNOWN = "unknown"


class LedgerPhase(StrEnum):
    STARTED = "started"
    FINISHED = "finished"


class RuntimeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = RUNTIME_SCHEMA_VERSION
    event_type: RuntimeEventType
    run_id: str
    operation_id: str | None = None
    attempt: int | None = None
    timestamp_ms: int
    duration_ms: int | None = None
    provider: str | None = None
    model: str | None = None
    status: RuntimeStatus
    failure_kind: RuntimeFailureKind | None = None
    token_usage: dict[str, int | None] = Field(default_factory=dict)
    fields: dict[str, Any] = Field(default_factory=dict)


class AttemptLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = RUNTIME_SCHEMA_VERSION
    operation_id: str
    attempt: int
    phase: LedgerPhase
    timestamp_ms: int
    status: RuntimeStatus
    side_effect_classification: SideEffectClassification
    idempotency_key: str | None = None
    failure_kind: RuntimeFailureKind | None = None


class AttemptLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = RUNTIME_SCHEMA_VERSION
    entries: list[AttemptLedgerEntry] = Field(default_factory=list)

    def record(self, entry: AttemptLedgerEntry) -> None:
        self.entries.append(entry)


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = 3
    total_elapsed_budget_seconds: float = 10
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 2
    jitter_seconds: float = 0


class RuntimeFailure(Exception):
    """Normalized runtime failure raised by generated provider and tool adapters."""

    def __init__(
        self,
        kind: RuntimeFailureKind,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        side_effect_committed: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after_seconds = retry_after_seconds
        self.side_effect_committed = side_effect_committed


T = TypeVar("T")


@dataclass(frozen=True)
class RetryOutcome[T]:
    status: RuntimeStatus
    attempts: int
    elapsed_seconds: float
    ledger: AttemptLedger
    result: T | None = None
    failure_kind: RuntimeFailureKind | None = None
    failure_message: str | None = None


class FailureContextPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    packet_type: Literal["failure_context"] = "failure_context"
    operation_id: str
    terminal_status: RuntimeStatus
    failure_kind: RuntimeFailureKind
    attempts: int
    user_goal_summary: str
    safe_message: str | None = None
    side_effect_state: str
    max_correction_attempts: int = 1
    max_output_tokens: int = 256


class HumanFailureSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    terminal_status: RuntimeStatus
    cause: RuntimeFailureKind | None = None
    attempts: int
    elapsed_ms: int
    side_effect_state: str
    evidence_artifact: str | None = None
    next_action: str


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class RandomSource(Protocol):
    def random(self) -> float: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class RuntimeJsonlWriter:
    """Append runtime events as redacted JSON Lines without disrupting target work."""

    def __init__(self, path: Path, *, max_field_chars: int = MAX_EVENT_FIELD_CHARS) -> None:
        self.path = path
        self.max_field_chars = max_field_chars
        self.failed_writes = 0

    def write_event(self, event: RuntimeEvent) -> bool:
        safe_payload = redact_runtime_payload(event.model_dump(mode="json"), self.max_field_chars)
        line = json.dumps(safe_payload, sort_keys=True, separators=(",", ":")) + "\n"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            self.failed_writes += 1
            return False
        return True


class RuntimeRetryExecutor:
    def __init__(
        self,
        policy: RetryPolicy,
        *,
        clock: Clock | None = None,
        random_source: RandomSource | None = None,
    ) -> None:
        self.policy = policy
        self.clock = clock or SystemClock()
        self.random_source = random_source

    def run(
        self,
        *,
        operation_id: str,
        side_effect_classification: SideEffectClassification,
        operation: Callable[[int], T],
        idempotency_key: str | None = None,
    ) -> RetryOutcome[T]:
        if (
            side_effect_classification is SideEffectClassification.IDEMPOTENT
            and not idempotency_key
        ):
            return RetryOutcome(
                status=RuntimeStatus.POLICY_BLOCKED,
                attempts=0,
                elapsed_seconds=0,
                ledger=AttemptLedger(),
                failure_kind=RuntimeFailureKind.POLICY_DENIAL,
            )

        ledger = AttemptLedger()
        started = self.clock.monotonic()
        attempt = 1
        retry_allowed = side_effect_classification in {
            SideEffectClassification.READ_ONLY,
            SideEffectClassification.IDEMPOTENT,
        }

        while True:
            now_ms = _timestamp_ms(self.clock.monotonic())
            ledger.record(
                AttemptLedgerEntry(
                    operation_id=operation_id,
                    attempt=attempt,
                    phase=LedgerPhase.STARTED,
                    timestamp_ms=now_ms,
                    status=RuntimeStatus.STARTED,
                    side_effect_classification=side_effect_classification,
                    idempotency_key=idempotency_key,
                )
            )
            try:
                result = operation(attempt)
            except RuntimeFailure as exc:
                terminal_status = self._terminal_status(
                    exc,
                    retry_allowed=retry_allowed,
                    side_effect_classification=side_effect_classification,
                    attempt=attempt,
                    started=started,
                )
                ledger.record(
                    AttemptLedgerEntry(
                        operation_id=operation_id,
                        attempt=attempt,
                        phase=LedgerPhase.FINISHED,
                        timestamp_ms=_timestamp_ms(self.clock.monotonic()),
                        status=terminal_status,
                        side_effect_classification=side_effect_classification,
                        idempotency_key=idempotency_key,
                        failure_kind=exc.kind,
                    )
                )
                if terminal_status is RuntimeStatus.RETRY_SCHEDULED:
                    delay = self._delay_for(attempt, exc)
                    self.clock.sleep(delay)
                    attempt += 1
                    continue
                return RetryOutcome(
                    status=terminal_status,
                    attempts=attempt,
                    elapsed_seconds=self.clock.monotonic() - started,
                    ledger=ledger,
                    failure_kind=exc.kind,
                    failure_message=str(exc),
                )

            ledger.record(
                AttemptLedgerEntry(
                    operation_id=operation_id,
                    attempt=attempt,
                    phase=LedgerPhase.FINISHED,
                    timestamp_ms=_timestamp_ms(self.clock.monotonic()),
                    status=RuntimeStatus.SUCCESS,
                    side_effect_classification=side_effect_classification,
                    idempotency_key=idempotency_key,
                )
            )
            return RetryOutcome(
                status=RuntimeStatus.SUCCESS,
                attempts=attempt,
                elapsed_seconds=self.clock.monotonic() - started,
                ledger=ledger,
                result=result,
            )

    def _terminal_status(
        self,
        failure: RuntimeFailure,
        *,
        retry_allowed: bool,
        side_effect_classification: SideEffectClassification,
        attempt: int,
        started: float,
    ) -> RuntimeStatus:
        if failure.side_effect_committed and side_effect_classification in {
            SideEffectClassification.UNKNOWN,
            SideEffectClassification.NON_IDEMPOTENT,
        }:
            return RuntimeStatus.COMMIT_STATUS_UNKNOWN
        if not retry_allowed:
            return RuntimeStatus.FAILED
        if failure.kind not in _RETRYABLE_FAILURES:
            return RuntimeStatus.FAILED
        if attempt >= self.policy.max_attempts:
            return RuntimeStatus.RETRY_EXHAUSTED
        delay = self._delay_for(attempt, failure)
        elapsed_after_delay = (self.clock.monotonic() - started) + delay
        if elapsed_after_delay > self.policy.total_elapsed_budget_seconds:
            return RuntimeStatus.RETRY_EXHAUSTED
        return RuntimeStatus.RETRY_SCHEDULED

    def _delay_for(self, attempt: int, failure: RuntimeFailure) -> float:
        if failure.retry_after_seconds is not None:
            return float(min(failure.retry_after_seconds, self.policy.max_delay_seconds))
        exponential = float(self.policy.base_delay_seconds) * (2 ** max(attempt - 1, 0))
        jitter = 0.0
        if self.random_source is not None and self.policy.jitter_seconds > 0:
            jitter = float(self.random_source.random()) * self.policy.jitter_seconds
        return float(min(exponential + jitter, self.policy.max_delay_seconds))


_RETRYABLE_FAILURES = {
    RuntimeFailureKind.TIMEOUT_BEFORE_RESPONSE,
    RuntimeFailureKind.RATE_LIMITED,
    RuntimeFailureKind.PROVIDER_UNAVAILABLE,
    RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT,
    RuntimeFailureKind.TOOL_FAILURE,
}


def redact_runtime_payload(value: Any, max_field_chars: int = MAX_EVENT_FIELD_CHARS) -> Any:
    if isinstance(value, MutableMapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if _SECRET_KEY_PATTERN.search(text_key):
                redacted[text_key] = "[redacted]"
            else:
                redacted[text_key] = redact_runtime_payload(item, max_field_chars)
        return redacted
    if isinstance(value, list):
        return [redact_runtime_payload(item, max_field_chars) for item in value]
    if isinstance(value, str):
        if _SECRET_VALUE_PATTERN.search(value):
            return "[redacted]"
        return value[:max_field_chars]
    return value


def build_failure_context_packet(
    *,
    outcome: RetryOutcome[Any],
    operation_id: str,
    user_goal: str,
    side_effect_classification: SideEffectClassification,
    max_goal_chars: int = 160,
) -> FailureContextPacket | None:
    if outcome.failure_kind is not RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT:
        return None
    if side_effect_classification is not SideEffectClassification.READ_ONLY:
        return None
    safe_goal = _safe_string(user_goal, max_goal_chars)
    safe_message = (
        _safe_string(outcome.failure_message, MAX_EVENT_FIELD_CHARS)
        if outcome.failure_message is not None
        else None
    )
    return FailureContextPacket(
        operation_id=operation_id,
        terminal_status=outcome.status,
        failure_kind=outcome.failure_kind,
        attempts=outcome.attempts,
        user_goal_summary=safe_goal,
        safe_message=safe_message,
        side_effect_state=_side_effect_state(outcome.status, side_effect_classification),
    )


def summarize_runtime_failure(
    *,
    outcome: RetryOutcome[Any],
    side_effect_classification: SideEffectClassification,
    evidence_artifact: Path | str | None = None,
) -> HumanFailureSummary:
    return HumanFailureSummary(
        terminal_status=outcome.status,
        cause=outcome.failure_kind,
        attempts=outcome.attempts,
        elapsed_ms=int(outcome.elapsed_seconds * 1000),
        side_effect_state=_side_effect_state(outcome.status, side_effect_classification),
        evidence_artifact=str(evidence_artifact) if evidence_artifact is not None else None,
        next_action=_next_action(outcome.status, outcome.failure_kind),
    )


def _safe_string(value: str, max_chars: int) -> str:
    redacted = redact_runtime_payload(value, max_chars)
    if not isinstance(redacted, str):
        return "[redacted]"
    return redacted


def _side_effect_state(
    status: RuntimeStatus,
    side_effect_classification: SideEffectClassification,
) -> str:
    if status is RuntimeStatus.COMMIT_STATUS_UNKNOWN:
        return "commit_status_unknown"
    if side_effect_classification in {
        SideEffectClassification.READ_ONLY,
        SideEffectClassification.IDEMPOTENT,
    }:
        return "retry_allowed_by_policy"
    return "not_retried_by_policy"


def _next_action(
    status: RuntimeStatus,
    failure_kind: RuntimeFailureKind | None,
) -> str:
    if status is RuntimeStatus.SUCCESS:
        return "Review runtime evidence before treating retry behavior as verified."
    if status is RuntimeStatus.COMMIT_STATUS_UNKNOWN:
        return "Inspect the external system before retrying this operation."
    if status is RuntimeStatus.RETRY_EXHAUSTED:
        return "Review the runtime JSONL evidence and provider availability before retrying."
    if failure_kind is RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT:
        return "Use the correction packet for one bounded model-output repair attempt."
    if failure_kind is RuntimeFailureKind.AUTHENTICATION_FAILED:
        return "Check provider credentials without printing secret values."
    if failure_kind is RuntimeFailureKind.CANCELLED:
        return "The operation was cancelled; rerun only if the side-effect state is understood."
    return "Review the runtime JSONL evidence and address the normalized failure cause."


def _timestamp_ms(value: float) -> int:
    return int(value * 1000)
