import json
from pathlib import Path

import pytest

from agentharness import GuardedCallFailed, guard, wrap
from agentharness.runtime import RuntimeFailureKind, RuntimeStatus


class FakeCompletions:
    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self.failures = failures
        self.error = error or TimeoutError("request timed out")
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if len(self.calls) <= self.failures:
            raise self.error
        return {"content": "ok"}


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeClient:
    def __init__(self, failures: int = 0, error: Exception | None = None) -> None:
        self.completions = FakeCompletions(failures, error)
        self.chat = FakeChat(self.completions)
        self.api_key = "sk-not-a-real-key"

    def close(self) -> None:
        self.closed = True


def test_wrap_passes_through_untouched_attributes() -> None:
    client = wrap(FakeClient(), log_path=None)

    assert client.api_key == "sk-not-a-real-key"
    client.close()


def test_wrap_retries_a_retryable_failure_and_returns_the_result() -> None:
    raw = FakeClient(failures=2)
    client = wrap(raw, log_path=None, max_attempts=3, timeout=5)

    result = client.chat.completions.create(model="demo", messages=[])

    assert result == {"content": "ok"}
    assert len(raw.completions.calls) == 3
    assert raw.completions.calls[0]["timeout"] == 5


def test_wrap_bounds_attempts_instead_of_retrying_forever() -> None:
    raw = FakeClient(failures=99)
    client = wrap(raw, log_path=None, max_attempts=2)

    with pytest.raises(GuardedCallFailed) as excinfo:
        client.chat.completions.create(model="demo", messages=[])

    assert excinfo.value.status is RuntimeStatus.RETRY_EXHAUSTED
    assert len(raw.completions.calls) == 2
    assert isinstance(excinfo.value.__cause__, TimeoutError)


def test_wrap_does_not_retry_an_unretryable_failure() -> None:
    raw = FakeClient(failures=99, error=PermissionError("invalid api key"))
    client = wrap(raw, log_path=None, max_attempts=5)

    with pytest.raises(GuardedCallFailed) as excinfo:
        client.chat.completions.create(model="demo", messages=[])

    assert excinfo.value.status is RuntimeStatus.FAILED
    assert len(raw.completions.calls) == 1


def test_wrap_does_not_override_a_caller_supplied_timeout() -> None:
    raw = FakeClient()
    client = wrap(raw, log_path=None, timeout=30)

    client.chat.completions.create(model="demo", messages=[], timeout=1)

    assert raw.completions.calls[0]["timeout"] == 1


def test_wrap_writes_one_redacted_event_per_attempt(tmp_path: Path) -> None:
    log = tmp_path / "runtime.jsonl"
    raw = FakeClient(failures=1)
    client = wrap(raw, log_path=log, max_attempts=2, run_id="test-run")

    client.chat.completions.create(model="demo", messages=[{"content": "sk-secret-value"}])

    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [event["status"] for event in events] == ["started", "failed", "started", "success"]
    assert events[1]["failure_kind"] == RuntimeFailureKind.TIMEOUT_BEFORE_RESPONSE.value
    assert all(event["run_id"] == "test-run" for event in events)
    assert "sk-secret-value" not in log.read_text(encoding="utf-8")


def test_guard_decorator_bounds_a_hand_rolled_call() -> None:
    attempts = []

    @guard(log_path=None, max_attempts=3)
    def ask(prompt: str) -> str:
        attempts.append(prompt)
        if len(attempts) < 3:
            raise TimeoutError("upstream timeout")
        return "answer"

    assert ask("hello") == "answer"
    assert len(attempts) == 3
