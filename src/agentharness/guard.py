"""One-line runtime harness for provider clients.

``wrap`` returns a transparent proxy around a provider SDK client. Attribute access and every
call the proxy does not recognize pass straight through, so the wrapped client keeps the SDK's
own surface. Calls whose attribute path matches a known provider generation method are routed
through the runtime: a request timeout, a bounded retry budget, normalized failure
classification, and a redacted JSONL event per attempt.

    from openai import OpenAI

    from agentharness import wrap

    client = wrap(OpenAI())
    client.chat.completions.create(model="gpt-4o", messages=[...])

``guard`` is the decorator form for a call the proxy cannot see, such as a provider reached
through a helper of your own. ``tool`` is the side-effect form: it declares what re-running a
function would do, and the runtime enforces that declaration.
"""

from __future__ import annotations

import functools
import inspect
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentharness.provider_adapters import classify_provider_error
from agentharness.providers import FailureKind
from agentharness.python_scanner import MODEL_CALL_SUFFIXES
from agentharness.runtime import (
    RetryPolicy,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeFailure,
    RuntimeFailureKind,
    RuntimeJsonlWriter,
    RuntimeRetryExecutor,
    RuntimeStatus,
    SideEffectClassification,
    redact_runtime_payload,
)

DEFAULT_LOG_PATH = Path(".agentharness") / "runtime.jsonl"
DRY_RUN_ENV_VAR = "AGENTHARNESS_DRY_RUN"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BUDGET_SECONDS = 90.0

_FAILURE_KIND_MAP = {
    FailureKind.TIMEOUT_BEFORE_RESPONSE: RuntimeFailureKind.TIMEOUT_BEFORE_RESPONSE,
    FailureKind.RATE_LIMITED: RuntimeFailureKind.RATE_LIMITED,
    FailureKind.PROVIDER_UNAVAILABLE: RuntimeFailureKind.PROVIDER_UNAVAILABLE,
    FailureKind.MALFORMED_RESPONSE: RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT,
    FailureKind.UNSUPPORTED_CAPABILITY: RuntimeFailureKind.INVALID_REQUEST,
    FailureKind.AUTHENTICATION_FAILED: RuntimeFailureKind.AUTHENTICATION_FAILED,
    FailureKind.INVALID_REQUEST: RuntimeFailureKind.INVALID_REQUEST,
    FailureKind.POLICY_DENIED: RuntimeFailureKind.POLICY_DENIAL,
    FailureKind.CANCELLED: RuntimeFailureKind.CANCELLED,
}

# Attribute paths that reach a guarded call, derived from the same suffix table the static
# scanner uses, so `harness scan` and `wrap` always agree on what counts as a provider call.
_GUARDED_PATHS = frozenset(suffix.lstrip(".") for suffix in MODEL_CALL_SUFFIXES)
_TRAVERSABLE_PREFIXES = frozenset(
    ".".join(parts[:index])
    for path in _GUARDED_PATHS
    for parts in [path.split(".")]
    for index in range(1, len(parts))
)


@dataclass(frozen=True)
class GuardConfig:
    """Bounds applied to every guarded call."""

    timeout: float | None = DEFAULT_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    budget_seconds: float = DEFAULT_BUDGET_SECONDS
    log_path: Path | None = DEFAULT_LOG_PATH
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")

    def policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_attempts=self.max_attempts,
            total_elapsed_budget_seconds=self.budget_seconds,
        )

    def writer(self) -> RuntimeJsonlWriter | None:
        return None if self.log_path is None else RuntimeJsonlWriter(Path(self.log_path))


def wrap(
    client: Any,
    *,
    timeout: float | None = DEFAULT_TIMEOUT_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    log_path: Path | str | None = DEFAULT_LOG_PATH,
    run_id: str | None = None,
) -> Any:
    """Return a proxy of ``client`` whose provider calls are bounded, classified, and logged."""
    config = GuardConfig(
        timeout=timeout,
        max_attempts=max_attempts,
        budget_seconds=budget_seconds,
        log_path=None if log_path is None else Path(log_path),
        **({} if run_id is None else {"run_id": run_id}),
    )
    return _GuardedProxy(client, config, ())


def guard[T](
    function: Callable[..., T] | None = None,
    *,
    timeout: float | None = DEFAULT_TIMEOUT_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    log_path: Path | str | None = DEFAULT_LOG_PATH,
    run_id: str | None = None,
) -> Callable[..., T] | Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator form of :func:`wrap` for a provider call the proxy cannot see."""
    config = GuardConfig(
        timeout=timeout,
        max_attempts=max_attempts,
        budget_seconds=budget_seconds,
        log_path=None if log_path is None else Path(log_path),
        **({} if run_id is None else {"run_id": run_id}),
    )

    def decorate(target: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(target)
        def guarded(*args: Any, **kwargs: Any) -> T:
            return call_guarded(target, config, target.__qualname__, args, kwargs)

        return guarded

    if function is not None:
        return decorate(function)
    return decorate


def call_guarded[T](
    target: Callable[..., T],
    config: GuardConfig,
    operation_id: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> T:
    """Run ``target`` under the retry policy, emitting one event per attempt."""
    kwargs = _with_timeout(target, kwargs, config.timeout)
    writer = config.writer()
    model = kwargs.get("model")
    last_error: Exception | None = None

    def operation(attempt: int) -> T:
        nonlocal last_error
        started = time.monotonic()
        _emit(
            writer,
            config,
            RuntimeEventType.MODEL_CALL_STARTED,
            operation_id=operation_id,
            attempt=attempt,
            status=RuntimeStatus.STARTED,
            model=model,
        )
        try:
            result = target(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            failure = classify_provider_error(exc)
            kind = _FAILURE_KIND_MAP.get(failure.kind, RuntimeFailureKind.PROVIDER_UNAVAILABLE)
            _emit(
                writer,
                config,
                RuntimeEventType.MODEL_CALL_FINISHED,
                operation_id=operation_id,
                attempt=attempt,
                status=RuntimeStatus.FAILED,
                model=model,
                failure_kind=kind,
                duration_ms=_elapsed_ms(started),
                fields={"error": type(exc).__name__},
            )
            raise RuntimeFailure(
                kind,
                failure.message,
                retry_after_seconds=failure.retry_after_seconds,
            ) from exc
        _emit(
            writer,
            config,
            RuntimeEventType.MODEL_CALL_FINISHED,
            operation_id=operation_id,
            attempt=attempt,
            status=RuntimeStatus.SUCCESS,
            model=model,
            duration_ms=_elapsed_ms(started),
        )
        return result

    outcome = RuntimeRetryExecutor(config.policy()).run(
        operation_id=operation_id,
        side_effect_classification=SideEffectClassification.READ_ONLY,
        operation=operation,
    )
    if outcome.status is RuntimeStatus.SUCCESS:
        return outcome.result  # type: ignore[return-value]
    raise GuardedCallFailed(operation_id, outcome.status, outcome.attempts, last_error)


class GuardedCallFailed(RuntimeError):
    """Raised when a guarded call exhausts its retry budget or fails without a retry."""

    def __init__(
        self,
        operation_id: str,
        status: RuntimeStatus,
        attempts: int,
        cause: Exception | None,
    ) -> None:
        detail = f" after {attempts} attempt(s)" if attempts else ""
        super().__init__(f"{operation_id} {status.value}{detail}: {cause}")
        self.operation_id = operation_id
        self.status = status
        self.attempts = attempts
        self.__cause__ = cause


class _GuardedProxy:
    """Transparent attribute proxy that guards only known provider call paths."""

    __slots__ = ("_agentharness_config", "_agentharness_path", "_agentharness_target")

    def __init__(self, target: Any, config: GuardConfig, path: tuple[str, ...]) -> None:
        object.__setattr__(self, "_agentharness_target", target)
        object.__setattr__(self, "_agentharness_config", config)
        object.__setattr__(self, "_agentharness_path", path)

    def __getattr__(self, name: str) -> Any:
        target = object.__getattribute__(self, "_agentharness_target")
        config = object.__getattribute__(self, "_agentharness_config")
        path = (*object.__getattribute__(self, "_agentharness_path"), name)
        attribute = getattr(target, name)
        joined = ".".join(path)
        if joined in _GUARDED_PATHS and callable(attribute):
            return _guarded_callable(attribute, config, joined)
        if joined in _TRAVERSABLE_PREFIXES:
            return _GuardedProxy(attribute, config, path)
        return attribute

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_agentharness_target"), name, value)

    def __repr__(self) -> str:
        target = object.__getattribute__(self, "_agentharness_target")
        return f"<agentharness.wrap {target!r}>"


def _guarded_callable(target: Callable[..., Any], config: GuardConfig, name: str) -> Any:
    @functools.wraps(target)
    def guarded(*args: Any, **kwargs: Any) -> Any:
        return call_guarded(target, config, name, args, kwargs)

    return guarded


def _with_timeout(
    target: Callable[..., Any],
    kwargs: dict[str, Any],
    timeout: float | None,
) -> dict[str, Any]:
    """Add the request timeout only when the callee accepts one and the caller omitted it."""
    if timeout is None or "timeout" in kwargs:
        return kwargs
    try:
        parameters = inspect.signature(target).parameters
    except (TypeError, ValueError):
        return kwargs
    accepts = "timeout" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    if not accepts:
        return kwargs
    return {**kwargs, "timeout": timeout}


def _emit(
    writer: RuntimeJsonlWriter | None,
    config: GuardConfig,
    event_type: RuntimeEventType,
    *,
    operation_id: str,
    attempt: int,
    status: RuntimeStatus,
    model: Any = None,
    failure_kind: RuntimeFailureKind | None = None,
    duration_ms: int | None = None,
    fields: dict[str, Any] | None = None,
) -> None:
    if writer is None:
        return
    writer.write_event(
        RuntimeEvent(
            event_type=event_type,
            run_id=config.run_id,
            operation_id=operation_id,
            attempt=attempt,
            timestamp_ms=int(time.time() * 1000),
            duration_ms=duration_ms,
            model=model if isinstance(model, str) else None,
            status=status,
            failure_kind=failure_kind,
            fields=redact_runtime_payload(fields or {}),
        )
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


# ---------------------------------------------------------------------------
# Tool side effects
# ---------------------------------------------------------------------------


class DryRunBlocked(RuntimeError):
    """Raised when a side-effecting tool is called while dry-run is active."""

    def __init__(self, operation_id: str) -> None:
        super().__init__(f"{operation_id} was not executed: dry-run is active.")
        self.operation_id = operation_id


class IdempotencyKeyRequired(RuntimeError):
    """Raised when a tool declared idempotent does not produce an idempotency key."""

    def __init__(self, operation_id: str) -> None:
        super().__init__(
            f"{operation_id} is declared idempotent, so it needs an idempotency_key. "
            "Pass a static string or a callable over the tool's arguments."
        )
        self.operation_id = operation_id


class CommitStatusUnknown(RuntimeError):
    """Raised when a non-idempotent tool failed and may or may not have committed."""

    def __init__(self, operation_id: str, cause: Exception | None) -> None:
        super().__init__(
            f"{operation_id} failed after the side effect may have committed. "
            f"It was not retried, because retrying could duplicate it: {cause}"
        )
        self.operation_id = operation_id
        self.__cause__ = cause


@dataclass
class _CommitLedger:
    """Results of idempotent tool calls already committed in this process."""

    entries: dict[tuple[str, str], Any] = field(default_factory=dict)

    def get(self, operation_id: str, key: str) -> tuple[bool, Any]:
        entry = self.entries.get((operation_id, key), _MISSING)
        return (entry is not _MISSING, None if entry is _MISSING else entry)

    def record(self, operation_id: str, key: str, result: Any) -> None:
        self.entries[(operation_id, key)] = result


_MISSING = object()

# ponytail: the commit ledger is per-process and in-memory, so a restart mid-run forgets what
# already committed. A durable ledger belongs on disk next to the JSONL log if runs need to
# survive a crash.
_COMMIT_LEDGER = _CommitLedger()


def dry_run_active() -> bool:
    """True when tools must record their intent instead of performing it."""
    return os.environ.get(DRY_RUN_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def tool[T](
    function: Callable[..., T] | None = None,
    *,
    side_effect: str | SideEffectClassification = SideEffectClassification.UNKNOWN,
    idempotency_key: str | Callable[..., str] | None = None,
    timeout: float | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    log_path: Path | str | None = DEFAULT_LOG_PATH,
    run_id: str | None = None,
) -> Callable[..., T] | Callable[[Callable[..., T]], Callable[..., T]]:
    """Declare what re-running this function would do, and enforce that declaration.

    ``side_effect`` is one of ``read_only``, ``idempotent``, ``transactional``,
    ``non_idempotent``, or ``unknown`` (the default, because an undeclared side effect is not
    safe to retry). Read-only and idempotent tools are retried on transient failures; an
    idempotent tool must supply an ``idempotency_key``, and a repeat call with a key that already
    committed in this process returns the recorded result instead of running again. A
    non-idempotent or unknown tool is never retried: if it fails, the commit status is unknown,
    and the caller is told so rather than being handed a silent duplicate.
    """
    classification = SideEffectClassification(side_effect)
    config = GuardConfig(
        timeout=timeout,
        max_attempts=max_attempts,
        budget_seconds=budget_seconds,
        log_path=None if log_path is None else Path(log_path),
        **({} if run_id is None else {"run_id": run_id}),
    )

    def decorate(target: Callable[..., T]) -> Callable[..., T]:
        operation_id = target.__qualname__

        @functools.wraps(target)
        def guarded(*args: Any, **kwargs: Any) -> T:
            return _call_tool(
                target,
                config,
                operation_id,
                classification,
                idempotency_key,
                args,
                kwargs,
            )

        return guarded

    if function is not None:
        return decorate(function)
    return decorate


def _call_tool[T](
    target: Callable[..., T],
    config: GuardConfig,
    operation_id: str,
    classification: SideEffectClassification,
    idempotency_key: str | Callable[..., str] | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> T:
    key = _resolve_idempotency_key(idempotency_key, args, kwargs)
    if classification is SideEffectClassification.IDEMPOTENT and not key:
        raise IdempotencyKeyRequired(operation_id)

    writer = config.writer()
    mutates = classification is not SideEffectClassification.READ_ONLY

    if mutates and dry_run_active():
        _emit(
            writer,
            config,
            RuntimeEventType.POLICY_BLOCK,
            operation_id=operation_id,
            attempt=0,
            status=RuntimeStatus.POLICY_BLOCKED,
            fields={"reason": "dry_run", "side_effect": classification.value},
        )
        raise DryRunBlocked(operation_id)

    if key is not None:
        committed, recorded = _COMMIT_LEDGER.get(operation_id, key)
        if committed:
            _emit(
                writer,
                config,
                RuntimeEventType.TOOL_CALL_FINISHED,
                operation_id=operation_id,
                attempt=0,
                status=RuntimeStatus.SUCCESS,
                fields={"reason": "already_committed", "idempotency_key": key},
            )
            return recorded  # type: ignore[no-any-return]

    kwargs = _with_timeout(target, kwargs, config.timeout)
    last_error: Exception | None = None
    retryable = classification in {
        SideEffectClassification.READ_ONLY,
        SideEffectClassification.IDEMPOTENT,
    }

    def operation(attempt: int) -> T:
        nonlocal last_error
        started = time.monotonic()
        _emit(
            writer,
            config,
            RuntimeEventType.TOOL_CALL_STARTED,
            operation_id=operation_id,
            attempt=attempt,
            status=RuntimeStatus.STARTED,
            fields={"side_effect": classification.value},
        )
        try:
            result = target(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            _emit(
                writer,
                config,
                RuntimeEventType.TOOL_CALL_FINISHED,
                operation_id=operation_id,
                attempt=attempt,
                status=RuntimeStatus.FAILED,
                duration_ms=_elapsed_ms(started),
                fields={"side_effect": classification.value, "error": type(exc).__name__},
            )
            raise RuntimeFailure(
                RuntimeFailureKind.TOOL_FAILURE,
                f"{operation_id} raised {type(exc).__name__}.",
                # A tool that is not safe to retry may already have committed, and nothing
                # observable proves otherwise. Say unknown rather than guessing.
                side_effect_committed=not retryable,
            ) from exc
        _emit(
            writer,
            config,
            RuntimeEventType.TOOL_CALL_FINISHED,
            operation_id=operation_id,
            attempt=attempt,
            status=RuntimeStatus.SUCCESS,
            duration_ms=_elapsed_ms(started),
            fields={"side_effect": classification.value},
        )
        return result

    outcome = RuntimeRetryExecutor(config.policy()).run(
        operation_id=operation_id,
        side_effect_classification=classification,
        operation=operation,
        idempotency_key=key,
    )
    if outcome.status is RuntimeStatus.SUCCESS:
        if key is not None:
            _COMMIT_LEDGER.record(operation_id, key, outcome.result)
        return outcome.result  # type: ignore[return-value]
    if outcome.status is RuntimeStatus.COMMIT_STATUS_UNKNOWN:
        raise CommitStatusUnknown(operation_id, last_error)
    raise GuardedCallFailed(operation_id, outcome.status, outcome.attempts, last_error)


def _resolve_idempotency_key(
    idempotency_key: str | Callable[..., str] | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str | None:
    if idempotency_key is None:
        return None
    if callable(idempotency_key):
        return str(idempotency_key(*args, **kwargs))
    return str(idempotency_key)


def reset_commit_ledger() -> None:
    """Forget which idempotent tool calls have committed. Intended for tests."""
    _COMMIT_LEDGER.entries.clear()
