import json
import os
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from autoharness.cli import app
from autoharness.reporter import canonical_json
from autoharness.scan import scan_repository

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures" / "repositories"
GOLDEN = Path(__file__).parent / "fixtures" / "golden"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_detects_phase_one_structural_facts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(
        repo / "agent.py",
        """
import os
import subprocess
from openai import OpenAI

app = object()

@app.command()
def main():
    client = OpenAI()
    client.chat.completions.create(model="demo", messages=[])
    subprocess.run(["echo", "hi"])
    open("state.txt", "w").write("x")
    getattr(client, "dynamic")
    try:
        os.system("echo risky")
    except Exception:
        pass

if __name__ == "__main__":
    main()
""",
    )

    report = scan_repository(repo)
    kinds = [fact.kind for fact in report.facts]

    assert report.summary.status == "complete"
    assert report.summary.functions == 1
    assert report.summary.cli_candidates == 2
    assert report.summary.model_call_candidates == 1
    assert report.summary.side_effect_candidates == 3
    assert report.summary.unknown_dynamic_patterns == 1
    assert "broad_exception_handler" in kinds


def test_scan_never_imports_or_executes_target_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    marker = tmp_path / "executed"
    write(
        repo / "setup.py",
        f"""
from pathlib import Path
Path({str(marker)!r}).write_text("executed")
def configure():
    return None
""",
    )

    report = scan_repository(repo)

    assert report.summary.python_files == 1
    assert not marker.exists()


def test_symlink_escape_and_secrets_are_excluded(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside.py"
    write(repo / "agent.py", "def ok():\n    return 1\n")
    write(repo / ".env", "OPENAI_API_KEY=sk-secret\n")
    write(repo / "private.pem", "-----BEGIN PRIVATE KEY-----\nsecret\n")
    outside.write_text("def outside():\n    return 2\n", encoding="utf-8")
    try:
        os.symlink(outside, repo / "linked.py")
    except OSError as exc:
        pytest.skip(f"symlink creation unsupported: {exc}")

    report = scan_repository(repo)
    excluded = {item.path: item.reason for item in report.repository.excluded_paths}
    report_json = canonical_json(report)

    assert excluded[".env"] == "secret_path"
    assert excluded["private.pem"] == "secret_path"
    assert excluded["linked.py"] == "symlink_outside_root"
    assert "sk-secret" not in report_json
    assert "PRIVATE KEY" not in report_json


def test_gitignore_and_autoharness_ignore_are_respected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(repo / ".gitignore", "ignored.py\n")
    write(repo / ".autoharnessignore", "local_only.py\n")
    write(repo / "ignored.py", "def ignored():\n    return 1\n")
    write(repo / "local_only.py", "def local():\n    return 1\n")
    write(repo / "agent.py", "def ok():\n    return 1\n")

    report = scan_repository(repo)
    excluded = {item.path: item.reason for item in report.repository.excluded_paths}
    included = {item.path for item in report.repository.included_files}

    assert excluded["ignored.py"] == "gitignore"
    assert excluded["local_only.py"] == "autoharness_ignore"
    assert "agent.py" in included


def test_scan_json_is_byte_stable_for_same_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(repo / "agent.py", "def ok():\n    return 1\n")

    first = canonical_json(scan_repository(repo))
    second = canonical_json(scan_repository(repo))

    assert first == second


def test_cli_human_and_json_share_counts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    output = tmp_path / "scan.json"
    write(repo / "agent.py", "def ok():\n    return 1\n")

    human = runner.invoke(app, ["scan", str(repo), "--output", str(output)])
    machine = runner.invoke(app, ["scan", str(repo), "--format", "json", "--output", str(output)])

    assert human.exit_code == 0
    assert machine.exit_code == 0
    payload = json.loads(machine.output)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert "AutoHarness scan is read-only" in human.output
    assert "Included files" in human.output
    assert payload["summary"] == artifact["summary"]
    assert str(payload["summary"]["included_files"]) in human.output


def test_parse_failure_is_reported_as_partial_scan(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    output = tmp_path / "scan.json"
    write(repo / "bad.py", "def broken(:\n    pass\n")

    report = scan_repository(repo)
    result = runner.invoke(app, ["scan", str(repo), "--output", str(output)])

    assert report.summary.status == "partial"
    assert report.summary.parse_failures == 1
    assert report.parse_failures[0].path == "bad.py"
    assert result.exit_code == 3
    assert output.exists()


def test_invalid_scan_path_exits_with_repository_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", str(tmp_path / "missing")])

    assert result.exit_code == 3
    assert "AH-S001" in result.output


def test_basic_scan_performance_does_not_go_quadratic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    for index in range(150):
        write(repo / f"pkg/file_{index}.py", f"def f_{index}():\n    return {index}\n")

    started = time.perf_counter()
    report = scan_repository(repo)
    elapsed = time.perf_counter() - started

    assert report.summary.python_files == 150
    assert report.summary.functions == 150
    assert elapsed < 2.0


def test_persistent_fixture_repositories_match_labels() -> None:
    basic = scan_repository(FIXTURES / "basic_agent")
    edge = scan_repository(FIXTURES / "edge_cases")
    unsupported = scan_repository(FIXTURES / "unsupported_text")

    edge_exclusions = {item.path: item.reason for item in edge.repository.excluded_paths}

    assert basic.summary.model_call_candidates == 1
    assert basic.summary.cli_candidates == 1
    assert edge.summary.side_effect_candidates == 2
    assert edge.summary.unknown_dynamic_patterns == 1
    assert edge_exclusions[".env"] == "secret_path"
    assert edge_exclusions["blob.bin"] == "binary_file"
    assert unsupported.summary.status == "unsupported"


def test_basic_agent_matches_golden_json_schema_fixture() -> None:
    report = scan_repository(FIXTURES / "basic_agent")
    payload = json.loads(canonical_json(report))
    payload["repository"]["root"] = "<fixture-root>"
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    assert normalized == (GOLDEN / "basic_agent_report.json").read_text(encoding="utf-8").strip()
