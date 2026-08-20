import json
from pathlib import Path

from typer.testing import CliRunner

from agentharness.cli import app

runner = CliRunner()

AGENT_SOURCE = """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
"""


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "agent.py").write_text(AGENT_SOURCE, encoding="utf-8")
    return repo


def _workflow(repo: Path) -> dict:
    return json.loads((repo / ".agentharness" / "workflow.json").read_text(encoding="utf-8"))


def test_audit_runs_scan_and_plan_without_touching_target_sources(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = (repo / "agent.py").read_bytes()

    result = runner.invoke(app, ["audit", str(repo)])

    assert result.exit_code == 0
    run = _workflow(repo)
    assert run["command"] == "audit"
    assert run["status"] == "completed"
    assert [stage["name"] for stage in run["stages"]] == ["scan", "plan"]
    assert (repo / "agent.py").read_bytes() == before
    assert sorted(p.name for p in repo.iterdir()) == [".agentharness", "agent.py"]


def test_check_exits_one_when_findings_reach_threshold(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = runner.invoke(app, ["check", str(repo), "--fail-on", "low", "--format", "json"])

    assert result.exit_code == 1
    run = json.loads(result.output)
    assert run == _workflow(repo)
    assert run["stages"][-1]["detail"].endswith("exceeded=True")


def test_check_passes_when_threshold_is_not_reached(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = runner.invoke(app, ["check", str(repo), "--fail-on", "critical"])

    assert result.exit_code == 0


def test_improve_without_approval_writes_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = runner.invoke(app, ["improve", str(repo)], input="n\n")

    assert result.exit_code == 4
    run = _workflow(repo)
    assert run["status"] == "declined"
    assert run["stages"][-1] == {
        "name": "approve",
        "status": "declined",
        "duration_ms": 0,
        "artifact": None,
        "detail": "No plan action was approved.",
    }
    assert not (repo / ".agentharness" / "generated").exists()


def test_improve_declined_at_apply_leaves_target_unwritten(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = runner.invoke(app, ["improve", str(repo)], input="y\nn\n")

    assert result.exit_code == 4
    run = _workflow(repo)
    assert run["status"] == "declined"
    assert [stage["name"] for stage in run["stages"]] == [
        "scan",
        "plan",
        "approve",
        "stage",
        "apply",
    ]
    assert not (repo / ".agentharness" / "generated").exists()


def test_improve_applies_approved_generation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = runner.invoke(app, ["improve", str(repo), "--yes", "--skip-verify"])

    assert result.exit_code == 0
    run = _workflow(repo)
    assert run["status"] == "incomplete"  # verification was skipped
    apply_stage = next(stage for stage in run["stages"] if stage["name"] == "apply")
    assert apply_stage["status"] == "completed"
    generated = sorted(p.name for p in (repo / ".agentharness" / "generated").iterdir())
    assert generated == [
        "agentharness_config.py",
        "agentharness_jsonl_logger.py",
        "agentharness_runner.py",
        "tests",
    ]


def test_approve_marks_supported_plan_actions_approved(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    runner.invoke(app, ["audit", str(repo)])
    plan_path = repo / ".agentharness" / "plan.json"

    result = runner.invoke(app, ["approve", str(plan_path), "--yes", "--format", "json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["approved_action_ids"]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["actions"][0]["approval_state"] == "approved"


def test_approve_declined_leaves_plan_unresolved(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    runner.invoke(app, ["audit", str(repo)])
    plan_path = repo / ".agentharness" / "plan.json"
    before = plan_path.read_bytes()

    result = runner.invoke(app, ["approve", str(plan_path)], input="n\n")

    assert result.exit_code == 4
    assert plan_path.read_bytes() == before
