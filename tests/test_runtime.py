import json
from pathlib import Path

from autoharness.runtime import (
    RetryPolicy,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeFailure,
    RuntimeFailureKind,
    RuntimeJsonlWriter,
    RuntimeRetryExecutor,
    RuntimeStatus,
    SideEffectClassification,
    build_failure_context_packet,
    summarize_runtime_failure,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeRandom:
    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


def test_unknown_side_effect_is_not_retried_after_fake_commit() -> None:
    clock = FakeClock()
    commits = 0

    def operation(_: int) -> str:
        nonlocal commits
        commits += 1
        raise RuntimeFailure(
            RuntimeFailureKind.TIMEOUT_BEFORE_RESPONSE,
            "timed out after fake commit",
            side_effect_committed=True,
        )

    outcome = RuntimeRetryExecutor(RetryPolicy(), clock=clock).run(
        operation_id="send-email",
        side_effect_classification=SideEffectClassification.UNKNOWN,
        operation=operation,
    )

    assert outcome.status is RuntimeStatus.COMMIT_STATUS_UNKNOWN
    assert outcome.attempts == 1
    assert commits == 1
    assert clock.sleeps == []
    assert [entry.phase for entry in outcome.ledger.entries] == ["started", "finished"]


def test_non_idempotent_operation_is_not_retried() -> None:
    attempts = 0

    def operation(_: int) -> str:
        nonlocal attempts
        attempts += 1
        raise RuntimeFailure(RuntimeFailureKind.PROVIDER_UNAVAILABLE, "temporary")

    outcome = RuntimeRetryExecutor(RetryPolicy(max_attempts=3)).run(
        operation_id="charge-card",
        side_effect_classification=SideEffectClassification.NON_IDEMPOTENT,
        operation=operation,
    )

    assert outcome.status is RuntimeStatus.FAILED
    assert outcome.attempts == 1
    assert attempts == 1


def test_rate_limit_respects_retry_after_attempts_and_elapsed_budget() -> None:
    clock = FakeClock()
    attempts = 0

    def operation(_: int) -> str:
        nonlocal attempts
        attempts += 1
        raise RuntimeFailure(
            RuntimeFailureKind.RATE_LIMITED,
            "slow down",
            retry_after_seconds=0.4,
        )

    outcome = RuntimeRetryExecutor(
        RetryPolicy(
            max_attempts=4,
            total_elapsed_budget_seconds=0.9,
            base_delay_seconds=0.1,
            max_delay_seconds=1,
        ),
        clock=clock,
    ).run(
        operation_id="model-call",
        side_effect_classification=SideEffectClassification.READ_ONLY,
        operation=operation,
    )

    assert outcome.status is RuntimeStatus.RETRY_EXHAUSTED
    assert outcome.attempts == 3
    assert attempts == 3
    assert clock.sleeps == [0.4, 0.4]
    assert [entry.status for entry in outcome.ledger.entries if entry.phase == "finished"] == [
        RuntimeStatus.RETRY_SCHEDULED,
        RuntimeStatus.RETRY_SCHEDULED,
        RuntimeStatus.RETRY_EXHAUSTED,
    ]


def test_idempotent_operation_requires_stable_key() -> None:
    outcome = RuntimeRetryExecutor(RetryPolicy()).run(
        operation_id="write-ticket",
        side_effect_classification=SideEffectClassification.IDEMPOTENT,
        operation=lambda _: "not called",
    )

    assert outcome.status is RuntimeStatus.POLICY_BLOCKED
    assert outcome.attempts == 0
    assert outcome.failure_kind is RuntimeFailureKind.POLICY_DENIAL


def test_retry_uses_seeded_jitter_deterministically() -> None:
    clock = FakeClock()
    attempts = 0

    def operation(_: int) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeFailure(RuntimeFailureKind.TIMEOUT_BEFORE_RESPONSE, "timeout")
        return "ok"

    outcome = RuntimeRetryExecutor(
        RetryPolicy(base_delay_seconds=0.2, jitter_seconds=0.5),
        clock=clock,
        random_source=FakeRandom(0.25),
    ).run(
        operation_id="read-model",
        side_effect_classification=SideEffectClassification.READ_ONLY,
        operation=operation,
    )

    assert outcome.status is RuntimeStatus.SUCCESS
    assert outcome.result == "ok"
    assert clock.sleeps == [0.325]


def test_jsonl_writer_redacts_bounds_and_preserves_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "runtime.jsonl"
    writer = RuntimeJsonlWriter(path, max_field_chars=12)
    event = RuntimeEvent(
        event_type=RuntimeEventType.MODEL_CALL_FINISHED,
        run_id="run-1",
        operation_id="op-1",
        attempt=1,
        timestamp_ms=1,
        status=RuntimeStatus.FAILED,
        failure_kind=RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT,
        fields={
            "raw_prompt": "secret prompt",
            "message": "hello\x1b[31m world that is long",
            "nested": {"token_value": "sk-live-secret-token"},
        },
    )

    assert writer.write_event(event)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["fields"]["raw_prompt"] == "[redacted]"
    assert payload["fields"]["nested"]["token_value"] == "[redacted]"
    assert payload["fields"]["message"] == "hello\x1b[31m w"


def test_jsonl_writer_failure_does_not_raise_or_fallback_unredacted(tmp_path: Path) -> None:
    blocked_path = tmp_path / "directory"
    blocked_path.mkdir()
    writer = RuntimeJsonlWriter(blocked_path)
    event = RuntimeEvent(
        event_type=RuntimeEventType.RUN_FINISHED,
        run_id="run-1",
        timestamp_ms=1,
        status=RuntimeStatus.FAILED,
        fields={"api_key": "sk-live-secret-token"},
    )

    assert not writer.write_event(event)
    assert writer.failed_writes == 1
    assert blocked_path.is_dir()


def test_malformed_output_builds_bounded_redacted_correction_packet() -> None:
    def operation(_: int) -> str:
        raise RuntimeFailure(
            RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT,
            "raw output had sk-secret-token",
        )

    outcome = RuntimeRetryExecutor(RetryPolicy(max_attempts=1)).run(
        operation_id="model-call",
        side_effect_classification=SideEffectClassification.READ_ONLY,
        operation=operation,
    )

    packet = build_failure_context_packet(
        outcome=outcome,
        operation_id="model-call",
        user_goal="summarize this without token value",
        side_effect_classification=SideEffectClassification.READ_ONLY,
        max_goal_chars=12,
    )

    assert packet is not None
    assert packet.failure_kind is RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT
    assert packet.safe_message == "[redacted]"
    assert packet.user_goal_summary == "[redacted]"
    assert packet.max_output_tokens == 256


def test_correction_packet_is_not_built_after_unknown_side_effect() -> None:
    outcome = RuntimeRetryExecutor(RetryPolicy(max_attempts=1)).run(
        operation_id="tool-call",
        side_effect_classification=SideEffectClassification.UNKNOWN,
        operation=lambda _: (_ for _ in ()).throw(
            RuntimeFailure(RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT, "bad output")
        ),
    )

    packet = build_failure_context_packet(
        outcome=outcome,
        operation_id="tool-call",
        user_goal="retry",
        side_effect_classification=SideEffectClassification.UNKNOWN,
    )

    assert packet is None


def test_human_failure_summary_explains_unknown_commit_next_action(tmp_path: Path) -> None:
    outcome = RuntimeRetryExecutor(RetryPolicy()).run(
        operation_id="send-email",
        side_effect_classification=SideEffectClassification.UNKNOWN,
        operation=lambda _: (_ for _ in ()).throw(
            RuntimeFailure(
                RuntimeFailureKind.TIMEOUT_BEFORE_RESPONSE,
                "timeout",
                side_effect_committed=True,
            )
        ),
    )

    summary = summarize_runtime_failure(
        outcome=outcome,
        side_effect_classification=SideEffectClassification.UNKNOWN,
        evidence_artifact=tmp_path / "runtime.jsonl",
    )

    assert summary.terminal_status is RuntimeStatus.COMMIT_STATUS_UNKNOWN
    assert summary.side_effect_state == "commit_status_unknown"
    assert "before retrying" in summary.next_action
    assert summary.evidence_artifact is not None


def test_cancellation_is_not_retried() -> None:
    attempts = 0

    def operation(_: int) -> str:
        nonlocal attempts
        attempts += 1
        raise RuntimeFailure(RuntimeFailureKind.CANCELLED, "cancelled")

    outcome = RuntimeRetryExecutor(RetryPolicy(max_attempts=3)).run(
        operation_id="model-call",
        side_effect_classification=SideEffectClassification.READ_ONLY,
        operation=operation,
    )

    assert outcome.status is RuntimeStatus.FAILED
    assert outcome.failure_kind is RuntimeFailureKind.CANCELLED
    assert attempts == 1
