from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from autoharness import __version__
from autoharness.config import ConfigOverrides, load_config
from autoharness.doctor import doctor_report
from autoharness.errors import AutoHarnessError, ErrorContext, render_error
from autoharness.generation import (
    apply_approved_plan,
    canonical_apply_preview_json,
    render_apply_preview,
    stage_apply_preview,
)
from autoharness.logging import configure_logging
from autoharness.output import ColorMode, OutputFormat, make_console, print_json
from autoharness.planning import (
    build_plan,
    canonical_plan_json,
    load_scan_report,
    render_plan_summary,
    write_plan,
)
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
    online: Annotated[
        bool,
        typer.Option(
            "--online",
            help="Build an evidence bundle for online enrichment; web calls require config.",
        ),
    ] = False,
    fail_on: Annotated[
        str | None,
        typer.Option(
            "--fail-on",
            help="Exit 1 when active findings at this severity or higher are present.",
        ),
    ] = None,
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
        report = scan_repository(
            path,
            max_file_bytes=max_file_bytes,
            online=online,
            web_evidence_config=config.web_evidence,
        )
        artifact_path = output if output.is_absolute() else Path.cwd() / output
        write_report(artifact_path, report)
        if OutputFormat(config.output_format) is OutputFormat.JSON:
            console.file.write(canonical_json(report) + "\n")
        else:
            render_human_summary(console, report, artifact_path=artifact_path)
        if report.summary.status in {"partial", "empty"}:
            raise typer.Exit(3)
        if fail_on is not None and _threshold_exceeded(
            report.summary.findings_by_severity, fail_on
        ):
            raise typer.Exit(1)
    except AutoHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def plan(
    scan_artifact: Annotated[
        Path,
        typer.Argument(help="Completed AutoHarness scan JSON artifact to plan from."),
    ] = Path(".autoharness/scan.json"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path for the canonical JSON plan artifact."),
    ] = Path(".autoharness/plan.json"),
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
    """Create a read-only review plan from a completed scan artifact."""
    try:
        config = load_config(
            ConfigOverrides(
                output_format=output_format,
                config_path=config_path,
                color=color,
            )
        )
        console = make_console(color=ColorMode(config.color), quiet=quiet)
        report, scan_hash = load_scan_report(scan_artifact)
        plan_artifact = build_plan(report, scan_hash=scan_hash, scan_path=scan_artifact)
        artifact_path = output if output.is_absolute() else Path.cwd() / output
        write_plan(artifact_path, plan_artifact)
        if OutputFormat(config.output_format) is OutputFormat.JSON:
            console.file.write(canonical_plan_json(plan_artifact) + "\n")
        else:
            render_plan_summary(console, plan_artifact, artifact_path=artifact_path)
        if plan_artifact.status == "blocked":
            raise typer.Exit(4)
    except AutoHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def apply(
    plan_artifact: Annotated[
        Path,
        typer.Argument(help="Approved AutoHarness plan JSON artifact to preview or apply."),
    ] = Path(".autoharness/plan.json"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path for the canonical JSON apply preview."),
    ] = Path(".autoharness/apply-preview.json"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Stage generated files without writing target files."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply approved generated files without an interactive prompt."),
    ] = False,
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
    """Preview or apply constrained generation from an approved plan artifact."""
    try:
        config = load_config(
            ConfigOverrides(
                output_format=output_format,
                config_path=config_path,
                color=color,
            )
        )
        console = make_console(color=ColorMode(config.color), quiet=quiet)
        artifact_path = output if output.is_absolute() else Path.cwd() / output
        if dry_run:
            preview = stage_apply_preview(
                plan_path=plan_artifact,
                output_path=artifact_path,
                dry_run=True,
            )
        else:
            confirmed = yes
            if not confirmed:
                try:
                    confirmed = typer.confirm(
                        "Apply approved generated files to the repository?",
                        default=False,
                    )
                except (typer.Abort, EOFError) as exc:
                    raise AutoHarnessError(
                        code="AH-G007",
                        message="Apply requires explicit approval.",
                        context=ErrorContext(
                            field="yes",
                            source="flag",
                            expected="--yes or interactive confirmation",
                            next_action=(
                                "Run with --dry-run first, then pass --yes or confirm the prompt."
                            ),
                        ),
                        exit_code=4,
                    ) from exc
            if not confirmed:
                if OutputFormat(config.output_format) is OutputFormat.JSON:
                    print_json(
                        console,
                        {
                            "schema_version": "1.0",
                            "artifact_type": "apply_result",
                            "status": "declined",
                            "message": "Apply declined; no target files were written.",
                        },
                    )
                else:
                    console.print("Apply declined: no target files were written.")
                return
            preview = apply_approved_plan(
                plan_path=plan_artifact,
                output_path=artifact_path,
                confirm=True,
            )
        if OutputFormat(config.output_format) is OutputFormat.JSON:
            console.file.write(canonical_apply_preview_json(preview) + "\n")
        else:
            render_apply_preview(console, preview, artifact_path=artifact_path)
    except AutoHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def doctor(
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
    """Report provider and evidence configuration without sending repository evidence."""
    try:
        config = load_config(
            ConfigOverrides(
                output_format=output_format,
                config_path=config_path,
                color=color,
            )
        )
        console = make_console(color=ColorMode(config.color), quiet=quiet)
        report = doctor_report(config)
        if OutputFormat(config.output_format) is OutputFormat.JSON:
            print_json(console, report)
        else:
            console.print("AutoHarness doctor does not send repository evidence.")
            model = report["model_assistance"]
            console.print(f"Model assistance: {'enabled' if model['enabled'] else 'disabled'}")
            console.print(f"Data policy: {model['data_policy']}")
            if model["route"]:
                for route in model["route"]:
                    missing = ", ".join(route["missing"]) if route["missing"] else "none"
                    console.print(
                        f"- {route['id']} {route['provider']} {route['model']} "
                        f"({route['locality']}), missing: {missing}"
                    )
            else:
                console.print("Route: none configured")
            web = report["web_evidence"]
            console.print(
                f"Web evidence: {'enabled' if web['enabled'] else 'disabled'} "
                f"({web['provider']}), credits: {web['max_credits_per_command']}"
            )
            sandbox = report["sandbox"]
            console.print(f"Sandbox backend: {sandbox['backend']} ({sandbox['status']})")
            for capability in sandbox["capabilities"]:
                console.print(
                    f"- {capability['name']}: {capability['status']} ({capability['evidence']})"
                )
    except AutoHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


def _threshold_exceeded(counts: dict[str, int], threshold: str) -> bool:
    order = ["low", "medium", "high", "critical"]
    normalized = threshold.lower()
    if normalized not in order:
        return False
    minimum = order.index(normalized)
    return any(counts.get(severity, 0) > 0 for severity in order[minimum:])
