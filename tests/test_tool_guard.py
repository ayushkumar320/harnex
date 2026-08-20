import json
from pathlib import Path

import pytest

from agentharness import (
    CommitStatusUnknown,
    DryRunBlocked,
    GuardedCallFailed,
    IdempotencyKeyRequired,
    tool,
)
from agentharness.guard import DRY_RUN_ENV_VAR, reset_commit_ledger


@pytest.fixture(autouse=True)
def _clean_ledger() -> None:
    reset_commit_ledger()


def test_read_only_tool_retries_a_transient_failure() -> None:
    attempts: list[int] = []

    @tool(side_effect="read_only", log_path=None, max_attempts=3)
    def read_config() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError("transient read error")
        return "config"

    assert read_config() == "config"
    assert len(attempts) == 3


def test_non_idempotent_tool_is_never_retried_and_reports_unknown_commit_status() -> None:
    sent: list[str] = []

    @tool(side_effect="non_idempotent", log_path=None, max_attempts=5)
    def send_email(to: str) -> None:
        sent.append(to)
        raise ConnectionError("connection dropped after send")

    with pytest.raises(CommitStatusUnknown) as excinfo:
        send_email("user@example.com")

    assert len(sent) == 1
    assert isinstance(excinfo.value.__cause__, ConnectionError)


def test_undeclared_side_effect_defaults_to_no_retry() -> None:
    calls: list[int] = []

    @tool(log_path=None, max_attempts=5)
    def mutate() -> None:
        calls.append(1)
        raise RuntimeError("boom")

    with pytest.raises(CommitStatusUnknown):
        mutate()

    assert len(calls) == 1


def test_idempotent_tool_requires_a_key() -> None:
    @tool(side_effect="idempotent", log_path=None)
    def write(path: str) -> str:
        return path

    with pytest.raises(IdempotencyKeyRequired):
        write("out.txt")


def test_idempotent_tool_does_not_run_twice_for_the_same_key(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    writes: list[str] = []

    @tool(
        side_effect="idempotent",
        idempotency_key=lambda path, data: f"{path}:{data}",
        log_path=None,
    )
    def write_file(path: Path, data: str) -> int:
        writes.append(data)
        return path.write_text(data, encoding="utf-8")

    first = write_file(target, "hello")
    second = write_file(target, "hello")

    assert first == second
    assert writes == ["hello"]


def test_idempotent_tool_retries_and_commits_once(tmp_path: Path) -> None:
    attempts: list[int] = []

    @tool(
        side_effect="idempotent",
        idempotency_key="fixed-key",
        log_path=None,
        max_attempts=3,
    )
    def flaky() -> str:
        attempts.append(1)
        if len(attempts) < 2:
            raise OSError("transient")
        return "committed"

    assert flaky() == "committed"
    assert flaky() == "committed"
    assert len(attempts) == 2


def test_dry_run_blocks_a_mutating_tool_and_records_the_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = tmp_path / "runtime.jsonl"
    performed: list[str] = []

    @tool(side_effect="non_idempotent", log_path=log, run_id="dry")
    def send(to: str) -> None:
        performed.append(to)

    monkeypatch.setenv(DRY_RUN_ENV_VAR, "1")

    with pytest.raises(DryRunBlocked):
        send("user@example.com")

    assert performed == []
    event = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert event["status"] == "policy_blocked"
    assert event["fields"]["reason"] == "dry_run"


def test_dry_run_still_allows_read_only_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    @tool(side_effect="read_only", log_path=None)
    def read() -> str:
        return "value"

    monkeypatch.setenv(DRY_RUN_ENV_VAR, "1")

    assert read() == "value"


def test_read_only_tool_exhausting_its_budget_raises_guarded_call_failed() -> None:
    @tool(side_effect="read_only", log_path=None, max_attempts=2)
    def always_fails() -> None:
        raise OSError("still broken")

    with pytest.raises(GuardedCallFailed) as excinfo:
        always_fails()

    assert excinfo.value.attempts == 2
