import shutil
from pathlib import Path

from typer.testing import CliRunner

from agentharness import __version__
from agentharness.cli import app

runner = CliRunner()
FIXTURE_REPO = Path(__file__).parent / "fixtures" / "repositories" / "basic_agent"


def test_help_describes_the_product() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Audit AI agent repositories" in result.output


def test_version_is_available_without_configuration() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_no_arguments_audits_the_current_directory(tmp_path: Path, monkeypatch) -> None:
    shutil.copytree(FIXTURE_REPO, tmp_path / "repo")
    monkeypatch.chdir(tmp_path / "repo")

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Workflow: audit" in result.output
    assert (tmp_path / "repo" / ".agentharness" / "scan.json").exists()


def test_json_output_mode_is_machine_readable(tmp_path: Path, monkeypatch) -> None:
    shutil.copytree(FIXTURE_REPO, tmp_path / "repo")
    monkeypatch.chdir(tmp_path / "repo")

    result = runner.invoke(app, ["--format", "json"])

    assert result.exit_code == 0
    assert '"command":"audit"' in result.output
    assert '"artifact_type":"workflow_run"' in result.output


def test_invalid_config_renders_without_traceback() -> None:
    result = runner.invoke(app, ["--format", "xml"])

    assert result.exit_code == 2
    assert "AH-C001" in result.output
    assert "output_format" in result.output
    assert "Traceback" not in result.output


def test_invalid_config_can_render_json_error() -> None:
    result = runner.invoke(app, ["--format", "json", "--color", "sparkle"])

    assert result.exit_code == 2
    assert '"code":"AH-C001"' in result.output
    assert '"field":"color"' in result.output


def test_no_color_environment_keeps_output_readable(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Audit AI agent repositories first" in result.output


def test_report_renders_markdown_from_a_scan(tmp_path: Path, monkeypatch) -> None:
    shutil.copytree(FIXTURE_REPO, tmp_path / "repo")
    monkeypatch.chdir(tmp_path / "repo")
    assert runner.invoke(app, []).exit_code == 0

    result = runner.invoke(app, ["report"])

    assert result.exit_code == 0
    markdown = (tmp_path / "repo" / ".agentharness" / "findings.md").read_text()
    assert markdown.startswith("# AgentHarness findings")
    assert "**What to change:**" in markdown


def test_report_without_a_scan_exits_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["report"])

    assert result.exit_code == 3
    assert "Run harness audit first" in result.output
    assert "Traceback" not in result.output
