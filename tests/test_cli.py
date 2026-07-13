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
