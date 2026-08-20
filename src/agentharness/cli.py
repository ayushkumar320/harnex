from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from agentharness import __version__
from agentharness.benchmark import (
    canonical_benchmark_json,
    render_benchmark_summary,
    run_benchmark,
    write_benchmark_report,
)
from agentharness.config import AppConfig, ConfigOverrides, load_config
from agentharness.doctor import doctor_report
from agentharness.errors import AgentHarnessError, ErrorContext, render_error
from agentharness.external_evidence import WebEvidenceConfig
from agentharness.generation import (
    apply_approved_plan,
    approve_plan_actions,
    canonical_apply_preview_json,
    render_apply_preview,
    stage_apply_preview,
)
from agentharness.logging import configure_logging
from agentharness.output import ColorMode, OutputFormat, make_console, print_json
from agentharness.planning import (
    HarnessPlan,
    build_plan,
    canonical_plan_json,
    load_scan_report,
    render_plan_summary,
    write_plan,
)
from agentharness.reporter import canonical_json, render_human_summary, write_report
from agentharness.scan import scan_repository
from agentharness.scan_models import AuditReport
from agentharness.verification import (
    canonical_verification_json,
    render_verification_summary,
    verify_repository,
    write_verification_report,
)
from agentharness.workflows import (
    WorkflowRecorder,
    WorkflowRun,
    WorkflowStage,
    canonical_workflow_json,
    render_workflow_summary,
    write_workflow_run,
)

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
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    """AgentHarness CLI bootstrap; product commands arrive through the build phases."""
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
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc
    except ValidationError as exc:
        error = AgentHarnessError(
            code="AH-C000",
            message="Internal CLI configuration validation failed.",
            details={"validation_error": str(exc)},
        )
        _render_cli_error(error, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(error.exit_code) from exc


def _render_cli_error(
    error: AgentHarnessError,
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
    ] = Path(".agentharness/scan.json"),
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
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def plan(
    scan_artifact: Annotated[
        Path,
        typer.Argument(help="Completed AgentHarness scan JSON artifact to plan from."),
    ] = Path(".agentharness/scan.json"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path for the canonical JSON plan artifact."),
    ] = Path(".agentharness/plan.json"),
    output_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format for this command: human or json."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def approve(
    plan_artifact: Annotated[
        Path,
        typer.Argument(help="Plan JSON artifact whose supported actions should be approved."),
    ] = Path(".agentharness/plan.json"),
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve without an interactive prompt."),
    ] = False,
    output_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format for this command: human or json."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    """Record explicit approval for supported generation actions in a plan artifact."""
    try:
        config, console = _workflow_common(output_format, config_path, color, quiet)
        if not (yes or _confirm(f"Approve supported actions in {plan_artifact}?")):
            console.print("Approval declined: the plan artifact was not modified.")
            raise typer.Exit(4)
        _plan, approved, skipped = approve_plan_actions(plan_artifact)
        if OutputFormat(config.output_format) is OutputFormat.JSON:
            print_json(
                console,
                {
                    "schema_version": "1.0",
                    "artifact_type": "approval_result",
                    "status": "approved",
                    "approved_action_ids": approved,
                    "skipped_action_ids": skipped,
                    "plan_artifact": str(plan_artifact),
                },
            )
        else:
            console.print(f"Approved actions: {', '.join(approved)}")
            if skipped:
                console.print(f"Left unapproved: {', '.join(skipped)}")
            console.print("Next: harness apply --dry-run, then harness apply --yes.")
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def apply(
    plan_artifact: Annotated[
        Path,
        typer.Argument(help="Approved AgentHarness plan JSON artifact to preview or apply."),
    ] = Path(".agentharness/plan.json"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path for the canonical JSON apply preview."),
    ] = Path(".agentharness/apply-preview.json"),
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
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
                    raise AgentHarnessError(
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
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def verify(
    path: Annotated[
        Path,
        typer.Argument(help="Repository directory to verify in a disposable workspace."),
    ] = Path("."),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path for the canonical JSON verification report."),
    ] = Path(".agentharness/verify.json"),
    keep_workspace: Annotated[
        bool,
        typer.Option(
            "--keep-workspace",
            help="Retain the disposable verification workspace for debugging.",
        ),
    ] = False,
    output_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format for this command: human or json."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    """Run deterministic verification checks in a disposable environment."""
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
        report = verify_repository(path, keep_workspace=keep_workspace)
        write_verification_report(artifact_path, report)
        if OutputFormat(config.output_format) is OutputFormat.JSON:
            console.file.write(canonical_verification_json(report) + "\n")
        else:
            render_verification_summary(console, report, artifact_path=artifact_path)
        if report.summary.get("failed", 0) > 0:
            raise typer.Exit(5)
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def benchmark(
    corpus: Annotated[
        Path,
        typer.Argument(help="Benchmark corpus JSON to run."),
    ] = Path("docs/benchmark/alpha-corpus.json"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path for the canonical JSON benchmark report."),
    ] = Path(".agentharness/benchmark.json"),
    output_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format for this command: human or json."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    """Run the labeled alpha benchmark corpus without live provider calls."""
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
        report = run_benchmark(corpus)
        write_benchmark_report(artifact_path, report)
        if OutputFormat(config.output_format) is OutputFormat.JSON:
            console.file.write(canonical_benchmark_json(report) + "\n")
        else:
            render_benchmark_summary(console, report, artifact_path=artifact_path)
        if report.alpha_decision == "blocked":
            raise typer.Exit(1)
    except AgentHarnessError as exc:
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
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
            console.print("AgentHarness doctor does not send repository evidence.")
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
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


def _threshold_exceeded(counts: dict[str, int], threshold: str) -> bool:
    order = ["low", "medium", "high", "critical"]
    normalized = threshold.lower()
    if normalized not in order:
        return False
    minimum = order.index(normalized)
    return any(counts.get(severity, 0) > 0 for severity in order[minimum:])


def _confirm(prompt: str) -> bool:
    """Ask for approval, treating an unavailable prompt as a refusal."""
    try:
        return typer.confirm(prompt, default=False)
    except (typer.Abort, EOFError):
        return False


def _workflow_common(
    output_format: str | None,
    config_path: Path | None,
    color: str | None,
    quiet: bool,
) -> tuple[AppConfig, Console]:
    config = load_config(
        ConfigOverrides(output_format=output_format, config_path=config_path, color=color)
    )
    configure_logging(config.log_level)
    return config, make_console(color=ColorMode(config.color), quiet=quiet)


def _finish_workflow(
    console: Console,
    config: AppConfig,
    run: WorkflowRun,
    artifact_path: Path,
) -> None:
    write_workflow_run(artifact_path, run)
    if OutputFormat(config.output_format) is OutputFormat.JSON:
        console.file.write(canonical_workflow_json(run) + "\n")
    else:
        render_workflow_summary(console, run, artifact_path=artifact_path)


def _scan_and_plan(
    recorder: WorkflowRecorder,
    path: Path,
    artifacts: Path,
    *,
    max_file_bytes: int,
    web_evidence_config: WebEvidenceConfig | None,
) -> tuple[AuditReport, HarnessPlan | None]:
    """Run the shared read-only scan and plan stages, returning both artifacts."""
    scan_path = artifacts / "scan.json"
    with recorder.stage("scan") as stage:
        report = scan_repository(
            path,
            max_file_bytes=max_file_bytes,
            online=False,
            web_evidence_config=web_evidence_config,
        )
        write_report(scan_path, report)
        stage["artifact"] = str(scan_path)
        stage["detail"] = f"status={report.summary.status}"
        if report.summary.status in {"partial", "empty"}:
            stage["status"] = "skipped"

    if report.summary.status != "complete":
        return report, None

    plan_path = artifacts / "plan.json"
    with recorder.stage("plan") as stage:
        loaded, scan_hash = load_scan_report(scan_path)
        plan_artifact = build_plan(loaded, scan_hash=scan_hash, scan_path=scan_path)
        write_plan(plan_path, plan_artifact)
        stage["artifact"] = str(plan_path)
        stage["detail"] = f"status={plan_artifact.status}"
        if plan_artifact.status != "review_required":
            stage["status"] = "skipped"
    return report, plan_artifact


@app.command()
def audit(
    path: Annotated[
        Path,
        typer.Argument(help="Repository directory to audit read-only."),
    ] = Path("."),
    artifacts: Annotated[
        Path,
        typer.Option("--artifacts", help="Directory for workflow artifacts."),
    ] = Path(".agentharness"),
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
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    """Scan and plan a repository in one read-only command."""
    try:
        config, console = _workflow_common(output_format, config_path, color, quiet)
        artifacts_dir = artifacts if artifacts.is_absolute() else path / artifacts
        recorder = WorkflowRecorder("audit")
        _, plan_artifact = _scan_and_plan(
            recorder,
            path,
            artifacts_dir,
            max_file_bytes=max_file_bytes,
            web_evidence_config=config.web_evidence,
        )
        if plan_artifact is None:
            next_action = "Resolve the reported scan status, then run harness audit again."
        elif plan_artifact.status == "review_required":
            next_action = "Review the plan, then run harness improve to stage approved changes."
        else:
            next_action = "No supported repair actions; review findings in the scan artifact."
        run = recorder.build(next_action=next_action)
        _finish_workflow(console, config, run, artifacts_dir / "workflow.json")
        if run.status == "failed":
            raise typer.Exit(3)
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def check(
    path: Annotated[
        Path,
        typer.Argument(help="Repository directory to check non-interactively."),
    ] = Path("."),
    fail_on: Annotated[
        str,
        typer.Option("--fail-on", help="Exit 1 when active findings reach this severity."),
    ] = "high",
    artifacts: Annotated[
        Path,
        typer.Option("--artifacts", help="Directory for workflow artifacts."),
    ] = Path(".agentharness"),
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
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    """Run a read-only CI check that fails on findings at or above a severity."""
    try:
        config, console = _workflow_common(output_format, config_path, color, quiet)
        artifacts_dir = artifacts if artifacts.is_absolute() else path / artifacts
        recorder = WorkflowRecorder("check")
        scan_path = artifacts_dir / "scan.json"
        exceeded = False
        with recorder.stage("scan") as stage:
            report = scan_repository(
                path,
                max_file_bytes=max_file_bytes,
                online=False,
                web_evidence_config=config.web_evidence,
            )
            write_report(scan_path, report)
            stage["artifact"] = str(scan_path)
            stage["detail"] = f"status={report.summary.status}"
            if report.summary.status in {"partial", "empty"}:
                stage["status"] = "skipped"
        with recorder.stage("threshold") as stage:
            exceeded = _threshold_exceeded(report.summary.findings_by_severity, fail_on)
            stage["detail"] = f"fail_on={fail_on} exceeded={exceeded}"
        next_action = (
            "Run harness audit for the full plan, then harness improve to repair findings."
            if exceeded
            else "No findings at or above the threshold; no action required."
        )
        run = recorder.build(next_action=next_action)
        _finish_workflow(console, config, run, artifacts_dir / "workflow.json")
        if exceeded:
            raise typer.Exit(1)
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc


@app.command()
def improve(
    path: Annotated[
        Path,
        typer.Argument(help="Repository directory to audit, stage, and repair."),
    ] = Path("."),
    artifacts: Annotated[
        Path,
        typer.Option("--artifacts", help="Directory for workflow artifacts."),
    ] = Path(".agentharness"),
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply the staged changes without an interactive prompt."),
    ] = False,
    skip_verify: Annotated[
        bool,
        typer.Option("--skip-verify", help="Do not run verification after applying changes."),
    ] = False,
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
        typer.Option("--config", help="Path to an AgentHarness YAML configuration file."),
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
    """Audit, stage approved changes, apply them after approval, and verify."""
    try:
        config, console = _workflow_common(output_format, config_path, color, quiet)
        artifacts_dir = artifacts if artifacts.is_absolute() else path / artifacts
        workflow_path = artifacts_dir / "workflow.json"
        recorder = WorkflowRecorder("improve")
        _, plan_artifact = _scan_and_plan(
            recorder,
            path,
            artifacts_dir,
            max_file_bytes=max_file_bytes,
            web_evidence_config=config.web_evidence,
        )
        if plan_artifact is None or plan_artifact.status != "review_required":
            run = recorder.build(
                next_action="Nothing to improve; review the scan artifact for reported findings.",
            )
            _finish_workflow(console, config, run, workflow_path)
            return

        plan_path = artifacts_dir / "plan.json"
        preview_path = artifacts_dir / "apply-preview.json"
        render_plan_summary(console, plan_artifact, artifact_path=plan_path)
        if not (yes or _confirm(f"Approve {len(plan_artifact.actions)} planned action(s)?")):
            recorder.stages.append(
                WorkflowStage(
                    name="approve",
                    status="declined",
                    duration_ms=0,
                    detail="No plan action was approved.",
                )
            )
            run = recorder.build(
                next_action="Review the plan artifact, then rerun harness improve to approve it.",
            )
            _finish_workflow(console, config, run, workflow_path)
            raise typer.Exit(4)
        with recorder.stage("approve") as stage:
            _plan, approved_ids, skipped_ids = approve_plan_actions(plan_path)
            stage["artifact"] = str(plan_path)
            stage["detail"] = f"approved={len(approved_ids)} skipped={len(skipped_ids)}"
        with recorder.stage("stage") as stage:
            preview = stage_apply_preview(
                plan_path=plan_path,
                output_path=preview_path,
                dry_run=True,
            )
            stage["artifact"] = str(preview_path)
            stage["detail"] = f"files={len(preview.files)}"
        render_apply_preview(console, preview, artifact_path=preview_path)

        if not (yes or _confirm("Apply these staged files to the repository?")):
            recorder.stages.append(
                WorkflowStage(
                    name="apply",
                    status="declined",
                    duration_ms=0,
                    detail="No target files were written.",
                )
            )
            run = recorder.build(
                next_action="Review the staged preview, then rerun harness improve --yes to apply.",
            )
            _finish_workflow(console, config, run, workflow_path)
            raise typer.Exit(4)

        with recorder.stage("apply") as stage:
            applied = apply_approved_plan(
                plan_path=plan_path,
                output_path=preview_path,
                confirm=True,
            )
            stage["artifact"] = str(preview_path)
            stage["detail"] = f"status={applied.status} files={len(applied.files)}"

        failed_checks = 0
        if skip_verify:
            recorder.stages.append(
                WorkflowStage(
                    name="verify",
                    status="skipped",
                    duration_ms=0,
                    detail="Verification skipped by --skip-verify.",
                )
            )
        else:
            verify_path = artifacts_dir / "verify.json"
            with recorder.stage("verify") as stage:
                verification = verify_repository(path, keep_workspace=False)
                write_verification_report(verify_path, verification)
                failed_checks = verification.summary.get("failed", 0)
                stage["artifact"] = str(verify_path)
                stage["detail"] = f"failed={failed_checks}"
                if failed_checks > 0:
                    stage["status"] = "failed"

        next_action = (
            "Verification failed; review the verify artifact and revert the applied files."
            if failed_checks
            else "Review the applied diff with git diff and commit it."
        )
        run = recorder.build(next_action=next_action)
        _finish_workflow(console, config, run, workflow_path)
        if failed_checks:
            raise typer.Exit(5)
    except AgentHarnessError as exc:
        _render_cli_error(exc, output_format=output_format, color=color, verbose=verbose)
        raise typer.Exit(exc.exit_code) from exc
