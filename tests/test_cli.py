from typer.testing import CliRunner

from autoharness import __version__
from autoharness.cli import app

runner = CliRunner()


def test_help_describes_the_product() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Audit AI agent repositories" in result.output


def test_version_is_available_without_configuration() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_no_arguments_shows_help() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_json_output_mode_is_machine_readable() -> None:
    result = runner.invoke(app, ["--format", "json"])

    assert result.exit_code == 0
    assert '"schema_version":"1.0"' in result.output
    assert '"status":"ok"' in result.output


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
