import hashlib
import importlib
import json
import os
import py_compile
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import autoharness.generation as generation
from autoharness.cli import app
from autoharness.errors import AutoHarnessError
from autoharness.generation import SUPPORTED_OUTPUT_FILES, apply_approved_plan, stage_apply_preview
from autoharness.planning import HarnessPlan, PlanAction, canonical_plan_json
from autoharness.reporter import write_report
from autoharness.scan import scan_repository

runner = CliRunner()


def test_apply_dry_run_stages_deterministic_generated_files(tmp_path: Path) -> None:
    repo, scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"

    first = stage_apply_preview(plan_path=plan_path, output_path=output_path, dry_run=True)
    second = stage_apply_preview(plan_path=plan_path, output_path=output_path, dry_run=True)

    assert first == second
    assert first.status == "staged"
    assert [item.path for item in first.files] == sorted(SUPPORTED_OUTPUT_FILES)
    assert output_path.exists()
    for item in first.files:
        staged = Path(item.staged_path)
        target = repo / item.path
        assert staged.exists()
        assert not target.exists()
        assert item.content_hash == _sha256(staged.read_bytes())
    assert scan_path.exists()


def test_apply_cli_dry_run_outputs_machine_readable_preview(tmp_path: Path) -> None:
    _repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "preview.json"

    result = runner.invoke(
        app,
        [
            "apply",
            str(plan_path),
            "--dry-run",
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == artifact
    assert payload["artifact_type"] == "apply_preview"
    assert payload["mode"] == "dry_run"


def test_apply_rejects_without_dry_run_or_approval(tmp_path: Path) -> None:
    _repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)

    result = runner.invoke(app, ["apply", str(plan_path)])

    assert result.exit_code == 4
    assert "AH-G007" in result.output


def test_apply_yes_writes_generated_files_and_transaction_journal(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"

    preview = apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)

    assert preview.status == "applied"
    assert preview.mode == "apply"
    assert preview.journal_path is not None
    assert Path(preview.journal_path).exists()
    for rel_path in SUPPORTED_OUTPUT_FILES:
        assert (repo / rel_path).is_file()
    payload = json.loads(Path(preview.journal_path).read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "apply_transaction_journal"
    assert payload["status"] == "applied"
    assert len(payload["files"]) == len(SUPPORTED_OUTPUT_FILES)


def test_apply_cli_yes_outputs_applied_preview(tmp_path: Path) -> None:
    _repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "preview.json"

    result = runner.invoke(
        app,
        ["apply", str(plan_path), "--yes", "--format", "json", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "applied"
    assert payload["mode"] == "apply"
    assert payload["journal_path"]


def test_apply_prompt_decline_is_clean_noop(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)

    result = runner.invoke(app, ["apply", str(plan_path)], input="n\n")

    assert result.exit_code == 0
    assert "Apply declined" in result.output
    assert not (repo / ".autoharness/generated/autoharness_config.py").exists()


def test_apply_prompt_accept_applies_files(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)

    result = runner.invoke(app, ["apply", str(plan_path)], input="y\n")

    assert result.exit_code == 0
    assert "Status: applied" in result.output
    assert (repo / ".autoharness/generated/autoharness_config.py").is_file()


def test_apply_clean_second_apply_is_allowed(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"

    first = apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)
    second = apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)

    assert first.status == "applied"
    assert second.status == "applied"
    assert (repo / ".autoharness/generated/autoharness_config.py").is_file()


def test_apply_reapply_preserves_append_only_user_edit(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"
    apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)
    target = repo / ".autoharness/generated/autoharness_config.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# user note\n", encoding="utf-8")

    apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)

    assert target.read_text(encoding="utf-8").endswith("\n# user note\n")


def test_apply_reapply_conflicts_on_generated_region_edit(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"
    apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)
    target = repo / ".autoharness/generated/autoharness_config.py"
    target.write_text("# edited inside generated base\n", encoding="utf-8")

    result = runner.invoke(app, ["apply", str(plan_path), "--yes", "--verbose"])

    assert result.exit_code == 4
    assert "AH-G010" in result.output
    assert target.read_text(encoding="utf-8") == "# edited inside generated base\n"


def test_apply_rolls_back_when_later_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"
    original_atomic_write = generation._atomic_write

    def fail_on_logger(path: Path, data: bytes) -> None:
        if path.name == "autoharness_jsonl_logger.py":
            raise OSError("simulated write failure")
        original_atomic_write(path, data)

    monkeypatch.setattr(generation, "_atomic_write", fail_on_logger)

    with pytest.raises(AutoHarnessError) as exc_info:
        apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)

    assert exc_info.value.code == "AH-G009"
    assert not (repo / ".autoharness/generated/autoharness_config.py").exists()
    journal_paths = list((repo / ".autoharness" / "transactions").glob("*.json"))
    assert len(journal_paths) == 1
    payload = json.loads(journal_paths[0].read_text(encoding="utf-8"))
    assert payload["status"] == "rolled_back"


def test_reapply_rollback_restores_existing_targets_and_generated_bases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"
    first = apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)
    assert first.journal_path is not None
    target = repo / ".autoharness/generated/autoharness_config.py"
    journal_path = Path(first.journal_path)
    base = generation._generated_base_path(
        journal_path, ".autoharness/generated/autoharness_config.py"
    )
    original_target = target.read_bytes()
    original_base = base.read_bytes()
    original_atomic_write = generation._atomic_write

    def fail_on_logger(path: Path, data: bytes) -> None:
        if path.name == "autoharness_jsonl_logger.py" and "generated-base" not in path.parts:
            raise OSError("simulated reapply failure")
        original_atomic_write(path, data)

    monkeypatch.setattr(generation, "_atomic_write", fail_on_logger)

    with pytest.raises(AutoHarnessError) as exc_info:
        apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)

    assert exc_info.value.code == "AH-G009"
    assert target.read_bytes() == original_target
    assert base.read_bytes() == original_base


def test_apply_cli_reports_structured_rollback_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    original_atomic_write = generation._atomic_write

    def fail_on_logger(path: Path, data: bytes) -> None:
        if path.name == "autoharness_jsonl_logger.py":
            raise OSError("simulated write failure")
        original_atomic_write(path, data)

    monkeypatch.setattr(generation, "_atomic_write", fail_on_logger)

    result = runner.invoke(app, ["apply", str(plan_path), "--yes"])

    assert result.exit_code == 5
    assert "AH-G009" in result.output
    assert not (repo / ".autoharness/generated/autoharness_config.py").exists()


def test_apply_rejects_special_file_target(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    target = repo / ".autoharness/generated/autoharness_config.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()

    result = runner.invoke(app, ["apply", str(plan_path), "--yes", "--verbose"])

    assert result.exit_code == 4
    assert "AH-G006" in result.output
    assert target.is_dir()


def test_generated_python_artifacts_compile_after_apply(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"

    apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)

    for rel_path in SUPPORTED_OUTPUT_FILES:
        if rel_path.endswith(".py"):
            py_compile.compile(str(repo / rel_path), doraise=True)


def test_generated_runtime_wrapper_runs_with_fake_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"
    apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)
    generated_root = repo / ".autoharness" / "generated"
    monkeypatch.syspath_prepend(str(generated_root))
    sys.modules.pop("autoharness_config", None)
    sys.modules.pop("autoharness_runner", None)
    runner_module = importlib.import_module("autoharness_runner")

    class FakeClock:
        def __init__(self) -> None:
            self.now = 0.0
            self.sleeps: list[float] = []

        def monotonic(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            self.sleeps.append(seconds)
            self.now += seconds

    calls = 0

    from autoharness.runtime import RuntimeFailure, RuntimeFailureKind

    def provider_with_runtime_failure(attempt: int) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if attempt == 1:
            raise RuntimeFailure(
                RuntimeFailureKind.RATE_LIMITED,
                "rate limited with sk-secret-token",
                retry_after_seconds=0.2,
            )
        return {"content": "ok", "raw_output": "sk-secret-token"}

    log_path = tmp_path / "runtime.jsonl"
    clock = FakeClock()
    result = runner_module.run_direct_provider(
        provider_with_runtime_failure,
        log_path=log_path,
        clock=clock,
    )

    assert result["status"] == "success"
    assert result["attempts"] == 2
    assert calls == 2
    assert clock.sleeps == [0.2]
    payload = log_path.read_text(encoding="utf-8")
    assert "retry_scheduled" in payload
    assert "sk-secret-token" not in payload


def test_generated_runtime_wrapper_returns_correction_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    output_path = tmp_path / "apply-preview.json"
    apply_approved_plan(plan_path=plan_path, output_path=output_path, confirm=True)
    generated_root = repo / ".autoharness" / "generated"
    monkeypatch.syspath_prepend(str(generated_root))
    sys.modules.pop("autoharness_config", None)
    sys.modules.pop("autoharness_runner", None)
    runner_module = importlib.import_module("autoharness_runner")
    from autoharness.runtime import RuntimeFailure, RuntimeFailureKind

    def provider(_: int) -> dict[str, object]:
        raise RuntimeFailure(
            RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT,
            "bad json with sk-secret-token",
        )

    result = runner_module.run_direct_provider(
        provider,
        user_goal="summarize safely",
        log_path=tmp_path / "runtime.jsonl",
    )

    assert result["status"] == "retry_exhausted"
    assert result["correction_packet"]["failure_kind"] == "malformed_structured_output"
    assert result["correction_packet"]["safe_message"] == "[redacted]"


def test_apply_rejects_unapproved_review_plan(tmp_path: Path) -> None:
    repo, scan_path, plan_path = _approved_plan_fixture(tmp_path)
    plan = _plan_for_scan(repo, scan_path, approval_state="unresolved", permission="review_only")
    _write_plan(plan_path, plan)

    result = runner.invoke(app, ["apply", str(plan_path), "--dry-run", "--format", "json"])

    assert result.exit_code == 4
    assert "AH-G004" in result.output


def test_apply_rejects_stale_source_scan_before_staging(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    (repo / "new_file.py").write_text("def changed():\n    return True\n", encoding="utf-8")

    result = runner.invoke(app, ["apply", str(plan_path), "--dry-run"])

    assert result.exit_code == 4
    assert "AH-P005" in result.output


def test_apply_rejects_unsafe_declared_output_path(tmp_path: Path) -> None:
    repo, scan_path, plan_path = _approved_plan_fixture(tmp_path)
    plan = _plan_for_scan(
        repo,
        scan_path,
        approval_state="approved",
        permission="write_generated_files",
        files=["../escape.py"],
    )
    _write_plan(plan_path, plan)

    result = runner.invoke(app, ["apply", str(plan_path), "--dry-run", "--verbose"])

    assert result.exit_code == 4
    assert "AH-G004" in result.output
    assert "../escape.py" in result.output


def test_apply_rejects_symlink_output_component(tmp_path: Path) -> None:
    repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        os.symlink(outside, repo / ".autoharness")
    except OSError as exc:
        pytest.skip(f"symlink creation unsupported: {exc}")

    result = runner.invoke(app, ["apply", str(plan_path), "--dry-run", "--verbose"])

    assert result.exit_code == 4
    assert "AH-G006" in result.output


def _approved_plan_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    scan_path = tmp_path / "scan.json"
    plan_path = tmp_path / "plan.json"
    (repo / "agent.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "agent.py").write_text(
        """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
""",
        encoding="utf-8",
    )
    write_report(scan_path, scan_repository(repo))
    _write_plan(plan_path, _plan_for_scan(repo, scan_path))
    return repo, scan_path, plan_path


def _plan_for_scan(
    repo: Path,
    scan_path: Path,
    *,
    approval_state: str = "approved",
    permission: str = "write_generated_files",
    files: list[str] | None = None,
) -> HarnessPlan:
    report = scan_repository(repo)
    finding = report.findings[0]
    return HarnessPlan(
        source_scan_hash=_sha256_text(scan_path.read_text(encoding="utf-8")),
        source_scan_path=str(scan_path),
        status="review_required",
        actions=[
            PlanAction(
                id="approved-direct-provider",
                title="Generate direct provider review skeleton",
                finding_ids=[finding.id],
                adapter="openai_compatible",
                permission=permission,
                files=list(files or SUPPORTED_OUTPUT_FILES),
                dependencies=[],
                side_effect_classification="read_only",
                verification=["Run generated smoke tests after review."],
                approval_state=approval_state,
            )
        ],
        blocked_findings=[],
        unresolved_decisions=[],
        next_action="Preview staged files with harness apply --dry-run.",
    )


def _write_plan(path: Path, plan: HarnessPlan) -> None:
    path.write_text(canonical_plan_json(plan) + "\n", encoding="utf-8")


def _sha256_text(text: str) -> str:
    return _sha256(text.encode("utf-8"))


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()
