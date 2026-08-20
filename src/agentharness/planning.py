"""Read-only Phase 3 plan artifact generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rich.console import Console
from rich.table import Table

from agentharness.errors import AgentHarnessError, ErrorContext
from agentharness.findings import Finding, GenerationState
from agentharness.reporter import fingerprint_for_inventory
from agentharness.repository import build_inventory
from agentharness.scan_models import AuditReport, StructuralFact


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
    approval_state: Literal["unresolved", "blocked", "approved"]
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


class ModelPlanActionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    finding_ids: list[str]
    adapter: str
    permission: str
    files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    side_effect_classification: str
    verification: list[str]
    approval_state: str
    evidence_ids: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class ModelPlanValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    message: str
    finding_id: str | None = None


class AcceptedModelPlanActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: list[PlanAction]
    rejected: list[ModelPlanValidationIssue]


def load_scan_report(path: Path) -> tuple[AuditReport, str]:
    try:
        raw = path.read_text(encoding="utf-8")
        report = AuditReport.model_validate_json(raw)
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise AgentHarnessError(
            code="AH-P001",
            message="Plan input is not a compatible scan artifact.",
            context=ErrorContext(
                field="scan",
                source="argument",
                expected="A completed AgentHarness audit_report JSON artifact.",
                next_action="Run harness scan first and pass its JSON output to harness plan.",
            ),
            exit_code=4,
        ) from exc
    return report, _sha256(raw)


GENERATED_OUTPUT_FILES = (
    ".agentharness/generated/agentharness_config.py",
    ".agentharness/generated/agentharness_jsonl_logger.py",
    ".agentharness/generated/agentharness_runner.py",
    ".agentharness/generated/tests/test_agentharness_smoke.py",
)


def build_plan(report: AuditReport, *, scan_hash: str, scan_path: Path) -> HarnessPlan:
    if report.summary.status != "complete":
        raise AgentHarnessError(
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
        next_action=("Review this plan, then run harness approve and harness apply --dry-run."),
    )


def validate_model_plan_action_candidates(
    candidates: list[ModelPlanActionCandidate],
    *,
    report: AuditReport,
) -> AcceptedModelPlanActions:
    findings_by_id = {finding.id: finding for finding in report.findings if not finding.suppressed}
    facts_by_id = {fact.evidence_hash: fact for fact in report.facts}
    accepted: list[PlanAction] = []
    rejected: list[ModelPlanValidationIssue] = []

    for candidate in candidates:
        issues = _model_plan_candidate_issues(candidate, findings_by_id, facts_by_id)
        if issues:
            rejected.extend(issues)
            continue
        accepted.append(_accepted_model_plan_action(candidate))
    accepted.sort(key=lambda item: item.id)
    return AcceptedModelPlanActions(accepted=accepted, rejected=rejected)


def canonical_plan_json(plan: HarnessPlan) -> str:
    payload = plan.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_plan(path: Path, plan: HarnessPlan) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_plan_json(plan) + "\n", encoding="utf-8")


def render_plan_summary(console: Console, plan: HarnessPlan, *, artifact_path: Path) -> None:
    console.print("AgentHarness plan is read-only: no files were written to the target repository.")
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
        title="Generate bounded provider runtime scaffolding for detected model call",
        finding_ids=[finding_id],
        adapter="openai_compatible",
        permission="write_generated_files",
        files=list(GENERATED_OUTPUT_FILES),
        dependencies=[],
        side_effect_classification="read_only",
        verification=[
            "Confirm provider calls route through a bounded adapter.",
            "Confirm failures are normalized and logged without secrets.",
        ],
        approval_state="unresolved",
    )


def _model_plan_candidate_issues(
    candidate: ModelPlanActionCandidate,
    findings_by_id: dict[str, Finding],
    facts_by_id: dict[str, StructuralFact],
) -> list[ModelPlanValidationIssue]:
    issues: list[ModelPlanValidationIssue] = []
    if not candidate.finding_ids:
        issues.append(_plan_issue("finding_ids", "At least one finding ID is required."))
    if candidate.permission != "review_only":
        issues.append(
            _plan_issue("permission", "Phase 3 model plans may only request review_only.")
        )
    if candidate.files:
        issues.append(_plan_issue("files", "Phase 3 model plans may not declare output files."))
    if candidate.dependencies:
        issues.append(_plan_issue("dependencies", "Phase 3 model plans may not add dependencies."))
    if candidate.side_effect_classification != "read_only":
        issues.append(
            _plan_issue(
                "side_effect_classification",
                "Review-only Phase 3 plan actions must be read_only.",
            )
        )
    if candidate.approval_state != "unresolved":
        issues.append(
            _plan_issue("approval_state", "The model cannot approve or block its own action.")
        )
    if not candidate.verification:
        issues.append(
            _plan_issue("verification", "At least one verification check must be declared.")
        )
    for path in candidate.files:
        if _unsafe_plan_path(path):
            issues.append(_plan_issue("files", f"Plan file path is not safe: {path}"))
    for finding_id in candidate.finding_ids:
        finding = findings_by_id.get(finding_id)
        if finding is None:
            issues.append(
                _plan_issue(
                    "finding_ids",
                    "Plan action cites a missing or suppressed finding.",
                    finding_id=finding_id,
                )
            )
            continue
        if not _is_supported_model_plan_finding(finding):
            issues.append(
                _plan_issue(
                    "finding_ids",
                    "Phase 3 model planning only accepts unresolved AH-R101 review actions.",
                    finding_id=finding_id,
                )
            )
        if not _adapter_matches_finding(candidate.adapter, finding, facts_by_id):
            issues.append(
                _plan_issue(
                    "adapter",
                    "Plan adapter is not supported by the cited finding evidence.",
                    finding_id=finding_id,
                )
            )
    valid_evidence_ids = set(facts_by_id)
    for evidence_id in candidate.evidence_ids:
        if evidence_id not in valid_evidence_ids:
            issues.append(
                _plan_issue("evidence_ids", f"Plan evidence ID does not exist: {evidence_id}")
            )
    return issues


def _accepted_model_plan_action(candidate: ModelPlanActionCandidate) -> PlanAction:
    digest = hashlib.sha256(
        "|".join(
            [
                candidate.title,
                candidate.adapter,
                *sorted(candidate.finding_ids),
                *sorted(candidate.evidence_ids),
            ]
        ).encode()
    ).hexdigest()[:10]
    return PlanAction(
        id=f"model-plan-action-{digest}",
        title=candidate.title,
        finding_ids=sorted(candidate.finding_ids),
        adapter=candidate.adapter,
        permission="review_only",
        files=[],
        dependencies=[],
        side_effect_classification="read_only",
        verification=candidate.verification,
        approval_state="unresolved",
    )


def _is_supported_model_plan_finding(finding: Finding) -> bool:
    return (
        getattr(finding, "rule_id", None) == "AH-R101"
        and getattr(finding, "generation", None) is GenerationState.REVIEW_REQUIRED
    )


def _adapter_matches_finding(
    adapter: str,
    finding: Finding,
    facts_by_id: dict[str, StructuralFact],
) -> bool:
    if adapter not in {"openai_compatible", "groq", "huggingface"}:
        return False
    evidence_items = getattr(finding, "evidence", [])
    for evidence in evidence_items:
        fact = facts_by_id.get(getattr(evidence, "id", ""))
        if fact is not None and adapter in getattr(fact, "adapter_candidates", []):
            return True
    return False


def _unsafe_plan_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    return candidate.is_absolute() or ".." in candidate.parts


def _plan_issue(
    field: str,
    message: str,
    *,
    finding_id: str | None = None,
) -> ModelPlanValidationIssue:
    return ModelPlanValidationIssue(field=field, message=message, finding_id=finding_id)


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_scan_compatibility(report: AuditReport) -> None:
    expected = fingerprint_for_inventory(report.repository).detector_versions
    if report.fingerprint.detector_versions != expected:
        raise AgentHarnessError(
            code="AH-P003",
            message="Plan input was produced by incompatible detector versions.",
            context=ErrorContext(
                field="fingerprint.detector_versions",
                source="scan artifact",
                expected="Current AgentHarness detector versions.",
                next_action="Run harness scan again with this AgentHarness version.",
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
        raise AgentHarnessError(
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
        raise AgentHarnessError(
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
