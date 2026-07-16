import json
from pathlib import Path

from typer.testing import CliRunner

from autoharness.cli import app
from autoharness.planning import ModelPlanActionCandidate, validate_model_plan_action_candidates
from autoharness.reporter import write_report
from autoharness.scan import scan_repository

runner = CliRunner()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_plan_from_completed_scan_produces_review_action(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scan_path = tmp_path / "scan.json"
    plan_path = tmp_path / "plan.json"
    write(
        repo / "agent.py",
        """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
""",
    )
    write_report(scan_path, scan_repository(repo))

    result = runner.invoke(
        app,
        ["plan", str(scan_path), "--format", "json", "--output", str(plan_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    artifact = json.loads(plan_path.read_text(encoding="utf-8"))
    assert payload == artifact
    assert payload["artifact_type"] == "harness_plan"
    assert payload["status"] == "review_required"
    assert payload["actions"][0]["permission"] == "review_only"
    assert payload["actions"][0]["approval_state"] == "unresolved"


def test_plan_rejects_partial_scan_artifact(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scan_path = tmp_path / "scan.json"
    write(repo / "bad.py", "def broken(:\n    pass\n")
    write_report(scan_path, scan_repository(repo))

    result = runner.invoke(app, ["plan", str(scan_path)])

    assert result.exit_code == 4
    assert "AH-P002" in result.output


def test_plan_rejects_stale_scan_artifact_when_repository_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scan_path = tmp_path / "scan.json"
    write(
        repo / "agent.py",
        """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
""",
    )
    write_report(scan_path, scan_repository(repo))
    write(repo / "new_file.py", "def new_behavior():\n    return 'changed'\n")

    result = runner.invoke(app, ["plan", str(scan_path)])

    assert result.exit_code == 4
    assert "AH-P005" in result.output


def test_plan_rejects_incompatible_detector_versions(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scan_path = tmp_path / "scan.json"
    write(
        repo / "agent.py",
        """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
""",
    )
    write_report(scan_path, scan_repository(repo))
    payload = json.loads(scan_path.read_text(encoding="utf-8"))
    payload["fingerprint"]["detector_versions"]["python_scanner"] = "old.detector.v0"
    scan_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    result = runner.invoke(app, ["plan", str(scan_path)])

    assert result.exit_code == 4
    assert "AH-P003" in result.output


def test_plan_with_only_blocked_findings_exits_four(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scan_path = tmp_path / "scan.json"
    write(
        repo / "agent.py",
        """
import subprocess

def run():
    subprocess.run(["echo", "hi"])
""",
    )
    write_report(scan_path, scan_repository(repo))

    result = runner.invoke(app, ["plan", str(scan_path), "--format", "json"])

    assert result.exit_code == 4
    payload = json.loads(result.output)
    assert payload["status"] == "blocked"
    assert payload["actions"] == []
    assert payload["blocked_findings"]


def test_model_plan_validator_accepts_review_only_instrumentation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(
        repo / "agent.py",
        """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
""",
    )
    report = scan_repository(repo)
    finding = report.findings[0]
    evidence_id = finding.evidence[0].id

    result = validate_model_plan_action_candidates(
        [
            ModelPlanActionCandidate(
                title="Review provider instrumentation for detected model call",
                finding_ids=[finding.id],
                adapter="openai_compatible",
                permission="review_only",
                files=[],
                dependencies=[],
                side_effect_classification="read_only",
                verification=["Confirm provider calls route through a bounded adapter."],
                approval_state="unresolved",
                evidence_ids=[evidence_id],
            )
        ],
        report=report,
    )

    assert result.rejected == []
    assert len(result.accepted) == 1
    assert result.accepted[0].finding_ids == [finding.id]
    assert result.accepted[0].permission == "review_only"


def test_model_plan_validator_rejects_write_permission_and_unsafe_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(
        repo / "agent.py",
        """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
""",
    )
    report = scan_repository(repo)

    result = validate_model_plan_action_candidates(
        [
            ModelPlanActionCandidate(
                title="Write generated instrumentation",
                finding_ids=[report.findings[0].id],
                adapter="openai_compatible",
                permission="write_generated_files",
                files=["../agent.py"],
                dependencies=["autoharness-runtime"],
                side_effect_classification="unknown",
                verification=[],
                approval_state="approved",
                evidence_ids=[report.findings[0].evidence[0].id],
            )
        ],
        report=report,
    )

    fields = {issue.field for issue in result.rejected}
    assert result.accepted == []
    assert fields >= {
        "permission",
        "files",
        "dependencies",
        "side_effect_classification",
        "verification",
        "approval_state",
    }


def test_model_plan_validator_rejects_missing_finding_and_unsupported_adapter(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    write(
        repo / "agent.py",
        """
import subprocess

def run():
    subprocess.run(["echo", "hi"])
""",
    )
    report = scan_repository(repo)

    result = validate_model_plan_action_candidates(
        [
            ModelPlanActionCandidate(
                title="Review unsupported action",
                finding_ids=["missing-finding", report.findings[0].id],
                adapter="made_up_adapter",
                permission="review_only",
                files=[],
                dependencies=[],
                side_effect_classification="read_only",
                verification=["Review manually."],
                approval_state="unresolved",
                evidence_ids=["missing-evidence"],
            )
        ],
        report=report,
    )

    fields = [issue.field for issue in result.rejected]
    assert result.accepted == []
    assert "finding_ids" in fields
    assert "adapter" in fields
    assert "evidence_ids" in fields
