import hashlib
import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from autoharness.cli import app
from autoharness.generation import SUPPORTED_OUTPUT_FILES, stage_apply_preview
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


def test_apply_rejects_without_dry_run(tmp_path: Path) -> None:
    _repo, _scan_path, plan_path = _approved_plan_fixture(tmp_path)

    result = runner.invoke(app, ["apply", str(plan_path)])

    assert result.exit_code == 4
    assert "AH-G002" in result.output


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
