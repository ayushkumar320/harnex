"""Read-only Phase 3 plan artifact generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rich.console import Console
from rich.table import Table

from autoharness.errors import AutoHarnessError, ErrorContext
from autoharness.findings import GenerationState
from autoharness.reporter import fingerprint_for_inventory
from autoharness.repository import build_inventory
from autoharness.scan_models import AuditReport


class PlanAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    finding_ids: list[str]
    adapter: str
    permission: Literal["review_only", "write_generated_files"]
    files: list[str]
    dependencies: list[str] = Field(default_factory=list)
    side_effect_classification: Literal["read_only", "unknown"]
    verification: list[str]
    approval_state: Literal["unresolved", "blocked"]
    blocked_reason: str | None = None


class HarnessPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["harness_plan"] = "harness_plan"
    source_scan_hash: str
    source_scan_path: str
    status: Literal["review_required", "no_supported_actions", "blocked"]
    actions: list[PlanAction]
    blocked_findings: list[str]
    unresolved_decisions: list[str]
    next_action: str


def load_scan_report(path: Path) -> tuple[AuditReport, str]:
    try:
        raw = path.read_text(encoding="utf-8")
        report = AuditReport.model_validate_json(raw)
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise AutoHarnessError(
            code="AH-P001",
            message="Plan input is not a compatible scan artifact.",
            context=ErrorContext(
                field="scan",
                source="argument",
                expected="A completed AutoHarness audit_report JSON artifact.",
                next_action="Run harness scan first and pass its JSON output to harness plan.",
            ),
            exit_code=4,
        ) from exc
    return report, _sha256(raw)


def build_plan(report: AuditReport, *, scan_hash: str, scan_path: Path) -> HarnessPlan:
    if report.summary.status != "complete":
        raise AutoHarnessError(
            code="AH-P002",
            message="Plan requires a completed scan artifact.",
            context=ErrorContext(
                field="summary.status",
                source="scan artifact",
                expected="complete",
                next_action="Resolve parse, empty, or unsupported scan status before planning.",
            ),
            exit_code=4,
        )
    _validate_scan_compatibility(report)
    _validate_scan_freshness(report)

    actions: list[PlanAction] = []
    blocked_findings: list[str] = []
    unresolved: list[str] = []
    for finding in [item for item in report.findings if not item.suppressed]:
        if finding.generation is GenerationState.REVIEW_REQUIRED and finding.rule_id == "AH-R101":
            actions.append(_instrumentation_action(finding.id))
            unresolved.append(f"Review model-call instrumentation for {finding.id}.")
        else:
            blocked_findings.append(finding.id)

    status: Literal["review_required", "no_supported_actions", "blocked"]
    if actions:
        status = "review_required"
    elif blocked_findings:
        status = "blocked"
    else:
        status = "no_supported_actions"

    return HarnessPlan(
        source_scan_hash=scan_hash,
        source_scan_path=str(scan_path),
        status=status,
        actions=actions,
        blocked_findings=blocked_findings,
        unresolved_decisions=unresolved,
        next_action=(
            "Review this plan. Later phases will add apply support after explicit approval."
        ),
    )


def canonical_plan_json(plan: HarnessPlan) -> str:
    payload = plan.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_plan(path: Path, plan: HarnessPlan) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_plan_json(plan) + "\n", encoding="utf-8")


def render_plan_summary(console: Console, plan: HarnessPlan, *, artifact_path: Path) -> None:
    console.print("AutoHarness plan is read-only: no files were written to the target repository.")
    console.print(f"Status: {plan.status}")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Actions", str(len(plan.actions)))
    table.add_row("Blocked findings", str(len(plan.blocked_findings)))
    table.add_row("Unresolved decisions", str(len(plan.unresolved_decisions)))
    console.print(table)
    for action in plan.actions:
        console.print(
            f"- {action.id} {action.title} ({action.permission}, approval: {action.approval_state})"
        )
    console.print(f"Detailed JSON: {artifact_path}")
    console.print(f"Next: {plan.next_action}")


def _instrumentation_action(finding_id: str) -> PlanAction:
    digest = hashlib.sha256(finding_id.encode("utf-8")).hexdigest()[:10]
    return PlanAction(
        id=f"plan-action-{digest}",
        title="Review provider instrumentation for detected model call",
        finding_ids=[finding_id],
        adapter="openai_compatible",
        permission="review_only",
        files=[],
        dependencies=[],
        side_effect_classification="read_only",
        verification=[
            "Confirm provider calls route through a bounded adapter.",
            "Confirm failures are normalized and logged without secrets.",
        ],
        approval_state="unresolved",
    )


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_scan_compatibility(report: AuditReport) -> None:
    expected = fingerprint_for_inventory(report.repository).detector_versions
    if report.fingerprint.detector_versions != expected:
        raise AutoHarnessError(
            code="AH-P003",
            message="Plan input was produced by incompatible detector versions.",
            context=ErrorContext(
                field="fingerprint.detector_versions",
                source="scan artifact",
                expected="Current AutoHarness detector versions.",
                next_action="Run harness scan again with this AutoHarness version.",
            ),
            exit_code=4,
            details={
                "actual": report.fingerprint.detector_versions,
                "expected": expected,
            },
        )


def _validate_scan_freshness(report: AuditReport) -> None:
    current_inventory = build_inventory(
        Path(report.repository.root),
        max_file_bytes=report.repository.scan_config.max_file_bytes,
    )
    current = fingerprint_for_inventory(current_inventory)
    if current.scan_config_hash != report.fingerprint.scan_config_hash:
        raise AutoHarnessError(
            code="AH-P004",
            message="Plan input uses a stale or changed scan configuration.",
            context=ErrorContext(
                field="fingerprint.scan_config_hash",
                source="scan artifact",
                expected="The current repository scan configuration.",
                next_action="Run harness scan again before planning.",
            ),
            exit_code=4,
            details={
                "actual": report.fingerprint.scan_config_hash,
                "expected": current.scan_config_hash,
            },
        )
    if current.inventory_hash != report.fingerprint.inventory_hash:
        raise AutoHarnessError(
            code="AH-P005",
            message="Plan input is stale because the repository snapshot changed.",
            context=ErrorContext(
                field="fingerprint.inventory_hash",
                source="scan artifact",
                expected="The current repository inventory fingerprint.",
                next_action="Run harness scan again before planning.",
            ),
            exit_code=4,
            details={
                "actual": report.fingerprint.inventory_hash,
                "expected": current.inventory_hash,
            },
        )
