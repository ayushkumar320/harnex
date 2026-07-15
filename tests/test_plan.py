import json
from pathlib import Path

from typer.testing import CliRunner

from autoharness.cli import app
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
