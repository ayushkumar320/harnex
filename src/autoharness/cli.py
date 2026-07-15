from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from autoharness import __version__
from autoharness.config import ConfigOverrides, load_config
from autoharness.errors import AutoHarnessError, render_error
from autoharness.logging import configure_logging
from autoharness.output import ColorMode, OutputFormat, make_console, print_json
from autoharness.reporter import canonical_json, render_human_summary, write_report
from autoharness.scan import scan_repository

app = typer.Typer(
    name="harness",
    help="Audit AI agent repositories first, then generate reviewable reliability controls.",
    no_args_is_help=False,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
    output_format: Annotated[
        str | None,
        typer.Option(
            "--format",
            help="Output format for command results: human or json.",
            metavar="FORMAT",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to an AutoHarness YAML configuration file."),
    ] = None,
    color: Annotated[
        str | None,
        typer.Option("--color", help="Color mode: auto, always, or never.", metavar="MODE"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show diagnostic context without raw secrets."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential human output."),
    ] = False,
) -> None:
    """AutoHarness CLI bootstrap; product commands arrive through the build phases."""
    try:
        config = load_config(
            ConfigOverrides(
                output_format=output_format,
                config_path=config_path,
                color=color,
            )
        )
        configure_logging(config.log_level)
        console = make_console(color=ColorMode(config.color), quiet=quiet)
        if ctx.invoked_subcommand is None:
            if OutputFormat(config.output_format) is OutputFormat.JSON:
                print_json(
                    console,
                    {
                        "schema_version": "1.0",
                        "command": "root",
                        "status": "ok",
                        "message": "No product command selected.",
                    },
                )
            else:
                console.print(ctx.get_help())
    except AutoHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc
    except ValidationError as exc:
        error = AutoHarnessError(
            code="AH-C000",
            message="Internal CLI configuration validation failed.",
            details={"validation_error": str(exc)},
        )
        _render_cli_error(error, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(error.exit_code) from exc


def _render_cli_error(
    error: AutoHarnessError,
    *,
    output_format: str | None,
    color: str | None,
    verbose: bool,
) -> None:
    json_requested = output_format == "json"
    safe_color = ColorMode.NEVER if color == "never" else ColorMode.AUTO
    console = make_console(color=safe_color, stderr=True)
    if json_requested:
        print_json(console, error.to_dict(verbose=verbose))
    else:
        render_error(console, error, verbose=verbose)


@app.command()
def scan(
    path: Annotated[
        Path,
        typer.Argument(help="Repository directory to scan without importing or executing it."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path for the canonical JSON scan report."),
    ] = Path(".autoharness/scan.json"),
    max_file_bytes: Annotated[
        int,
        typer.Option("--max-file-bytes", help="Maximum file size to read during inventory."),
    ] = 1_000_000,
    output_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format for this command: human or json."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to an AutoHarness YAML configuration file."),
    ] = None,
    color: Annotated[
        str | None,
        typer.Option("--color", help="Color mode: auto, always, or never."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show diagnostic context without raw secrets."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential human output."),
    ] = False,
) -> None:
    """Read-only structural scan of a Python agent repository."""
    try:
        config = load_config(
            ConfigOverrides(
                output_format=output_format,
                config_path=config_path,
                color=color,
            )
        )
        configure_logging(config.log_level)
        console = make_console(color=ColorMode(config.color), quiet=quiet)
        report = scan_repository(path, max_file_bytes=max_file_bytes)
        artifact_path = output if output.is_absolute() else Path.cwd() / output
        write_report(artifact_path, report)
        if OutputFormat(config.output_format) is OutputFormat.JSON:
            console.file.write(canonical_json(report) + "\n")
        else:
            render_human_summary(console, report, artifact_path=artifact_path)
        if report.summary.status in {"partial", "empty"}:
            raise typer.Exit(3)
    except AutoHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc
