import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

import autoharness.verification as verification
from autoharness.cli import app
from autoharness.errors import AutoHarnessError
from autoharness.reporter import write_report
from autoharness.sandbox import (
    SandboxBackendKind,
    SandboxCapability,
    SandboxCapabilityReport,
    SandboxCapabilityStatus,
    SandboxCommandResult,
    SandboxResult,
)
from autoharness.scan import scan_repository

runner = CliRunner()


class FakeSandboxBackend:
    def probe(self) -> SandboxCapabilityReport:
        return SandboxCapabilityReport(
            backend=SandboxBackendKind.DOCKER,
            status=SandboxCapabilityStatus.SUPPORTED,
            capabilities=[
                SandboxCapability(
                    name="fake_sandbox",
                    status=SandboxCapabilityStatus.SUPPORTED,
                    evidence="fake backend for deterministic tests",
                )
            ],
            containment_summary=["fake containment"],
        )

    def run(self, request) -> SandboxResult:
        return SandboxResult(
            backend=SandboxBackendKind.DOCKER,
            status=SandboxCommandResult.COMPLETED,
            exit_code=0,
            stdout=json.dumps(
                {
                    "uid": 65532,
                    "source_write_blocked": True,
                    "network_denied": True,
                    "output_written": "ok",
                }
            ),
            stderr="",
            duration_ms=1,
            capability_report=self.probe(),
            containment_summary=["fake containment"],
        )


def test_verify_repository_reports_passed_controls_and_draft_evals(tmp_path: Path) -> None:
    repo = _repo_fixture(tmp_path)
    before = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))

    report = verification.verify_repository(repo, sandbox_backend=FakeSandboxBackend())

    statuses = {check.id: check.status for check in report.checks}
    assert statuses["runtime_retry_redaction"] == "passed"
    assert statuses["duplicate_side_effect_block"] == "passed"
    assert statuses["sandbox_containment"] == "passed"
    assert statuses["original_tree_unchanged"] == "passed"
    assert statuses["semantic_eval_drafts"] == "requires_approval"
    assert report.cleanup_status == "removed"
    assert report.summary["failed"] == 0
    after = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
    assert after == before


def test_verify_cli_outputs_machine_readable_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = _repo_fixture(tmp_path)
    output = tmp_path / "verify.json"
    monkeypatch.setattr(verification, "DockerSandboxBackend", FakeSandboxBackend)

    result = runner.invoke(
        app,
        ["verify", str(repo), "--format", "json", "--output", str(output)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert payload == artifact
    assert payload["artifact_type"] == "verification_report"
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["requires_approval"] == 1


def test_verify_reports_failed_sandbox_capability(tmp_path: Path) -> None:
    repo = _repo_fixture(tmp_path)

    class MissingSandbox(FakeSandboxBackend):
        def probe(self) -> SandboxCapabilityReport:
            return SandboxCapabilityReport(
                backend=SandboxBackendKind.DOCKER,
                status=SandboxCapabilityStatus.UNSUPPORTED,
                capabilities=[
                    SandboxCapability(
                        name="docker_daemon",
                        status=SandboxCapabilityStatus.UNSUPPORTED,
                        evidence="not running",
                    )
                ],
                containment_summary=[],
            )

    report = verification.verify_repository(repo, sandbox_backend=MissingSandbox())

    sandbox = next(check for check in report.checks if check.id == "sandbox_containment")
    assert sandbox.status == "failed"
    assert report.summary["failed"] == 1


def test_verify_rejects_symlink_before_reading_external_target(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("sk-external-secret-value", encoding="utf-8")
    try:
        os.symlink(outside, repo / "linked-secret.txt")
    except OSError as exc:
        pytest.skip(f"symlink creation unsupported: {exc}")

    with pytest.raises(AutoHarnessError) as exc_info:
        verification.verify_repository(repo, sandbox_backend=FakeSandboxBackend())

    assert exc_info.value.code == "AH-V002"
    assert "sk-external-secret-value" not in str(exc_info.value.details)


def _repo_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "Example: ask the agent to summarize safely.\n",
        encoding="utf-8",
    )
    (repo / "agent.py").write_text(
        """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
""",
        encoding="utf-8",
    )
    scan_path = repo / ".autoharness" / "scan.json"
    write_report(scan_path, scan_repository(repo))
    return repo
