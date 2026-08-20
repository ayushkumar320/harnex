"""Scan report assembly, canonical JSON, and human rendering."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.table import Table

from agentharness.findings import (
    DETECTOR_VERSION as FINDING_DETECTOR_VERSION,
)
from agentharness.findings import (
    Finding,
    derive_findings,
    finding_counts,
    load_suppressions,
    unsuppressed_findings,
)
from agentharness.python_scanner import DETECTOR_VERSION as PYTHON_SCANNER_VERSION
from agentharness.scan_models import (
    ArtifactFingerprint,
    AuditReport,
    ParseFailure,
    RepositoryInventory,
    ScanSummary,
    StructuralFact,
)


def build_report(
    *,
    inventory: RepositoryInventory,
    facts: list[StructuralFact],
    parse_failures: int,
) -> AuditReport:
    counts = _count_facts(facts)
    root = Path(inventory.root)
    python_files = inventory.language_counts.get("python", 0)
    status: Literal["complete", "partial", "empty", "unsupported"]
    if not inventory.included_files:
        status = "empty"
    elif parse_failures:
        status = "partial"
    elif python_files == 0:
        status = "unsupported"
    else:
        status = "complete"

    summary = ScanSummary(
        status=status,
        included_files=len(inventory.included_files),
        excluded_paths=len(inventory.excluded_paths),
        python_files=python_files,
        parse_failures=parse_failures,
        total_facts=len(facts),
        functions=counts["function"],
        cli_candidates=counts["cli_candidate"],
        model_call_candidates=counts["model_call_candidate"],
        side_effect_candidates=counts["side_effect_candidate"],
        unknown_dynamic_patterns=counts["unknown_dynamic_pattern"],
    )
    findings = derive_findings(
        facts,
        inventory.excluded_paths,
        suppressions=load_suppressions(root),
    )
    active_findings = unsuppressed_findings(findings)
    summary = summary.model_copy(
        update={
            "findings_total": len(active_findings),
            "findings_by_severity": finding_counts(active_findings),
            "suppressed_findings": len(findings) - len(active_findings),
        }
    )
    return AuditReport(
        repository=inventory,
        fingerprint=fingerprint_for_inventory(inventory),
        facts=facts,
        parse_failures=[],
        findings=findings,
        summary=summary,
        next_action="Review findings, then run harness plan on the JSON report.",
    )


def attach_parse_failures(report: AuditReport, parse_failures: list[ParseFailure]) -> AuditReport:
    return report.model_copy(update={"parse_failures": parse_failures})


def canonical_json(report: AuditReport) -> str:
    payload = report.model_dump(mode="json", exclude_none=True, by_alias=False)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_report(path: Path, report: AuditReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(report) + "\n", encoding="utf-8")


def fingerprint_for_inventory(inventory: RepositoryInventory) -> ArtifactFingerprint:
    stable_inventory = inventory.model_copy(
        update={
            "excluded_paths": [
                item
                for item in inventory.excluded_paths
                if not (
                    item.path == ".agentharness" and item.reason == "default_excluded_directory"
                )
            ]
        }
    )
    inventory_payload = stable_inventory.model_dump(
        mode="json",
        include={"included_files", "excluded_paths", "language_counts"},
    )
    config_payload = stable_inventory.scan_config.model_dump(mode="json")
    return ArtifactFingerprint(
        inventory_hash=_sha256_json(inventory_payload),
        scan_config_hash=_sha256_json(config_payload),
        detector_versions={
            "findings": FINDING_DETECTOR_VERSION,
            "python_scanner": PYTHON_SCANNER_VERSION,
        },
    )


def render_human_summary(console: Console, report: AuditReport, *, artifact_path: Path) -> None:
    summary = report.summary
    console.print("AgentHarness scan is read-only: target code was parsed as data, not executed.")
    console.print(f"Repository: {report.repository.root}")
    console.print(f"Status: {summary.status}")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Included files", str(summary.included_files))
    table.add_row("Excluded paths", str(summary.excluded_paths))
    table.add_row("Python files", str(summary.python_files))
    table.add_row("Parse failures", str(summary.parse_failures))
    table.add_row("Functions", str(summary.functions))
    table.add_row("CLI candidates", str(summary.cli_candidates))
    table.add_row("Model call candidates", str(summary.model_call_candidates))
    table.add_row("Side-effect candidates", str(summary.side_effect_candidates))
    table.add_row("Unknown dynamic patterns", str(summary.unknown_dynamic_patterns))
    table.add_row("Findings", str(summary.findings_total))
    table.add_row("Suppressed findings", str(summary.suppressed_findings))
    for severity, count in summary.findings_by_severity.items():
        if count:
            table.add_row(f"Findings {severity}", str(count))
    if report.evidence_bundle is not None:
        table.add_row("Local evidence chunks", str(len(report.evidence_bundle.local_evidence)))
        table.add_row(
            "External evidence chunks",
            str(len(report.evidence_bundle.external_evidence)),
        )
    console.print(table)
    if report.findings:
        console.print("Highest-impact findings:")
        for finding in report.findings[:5]:
            evidence = finding.evidence[0]
            location = evidence.path
            if evidence.line is not None:
                location = f"{location}:{evidence.line}"
            console.print(
                f"- {finding.rule_id} {finding.title} "
                f"({finding.severity.value}, {finding.support.value}) at {location}"
            )
    console.print(f"Detailed JSON: {artifact_path}")
    console.print(f"Next: {report.next_action}")


def _count_facts(facts: list[StructuralFact]) -> dict[str, int]:
    counts = {
        "function": 0,
        "cli_candidate": 0,
        "model_call_candidate": 0,
        "side_effect_candidate": 0,
        "unknown_dynamic_pattern": 0,
    }
    for fact in facts:
        if fact.kind in counts:
            counts[fact.kind] += 1
    return counts


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


_SEVERITY_ORDER = ("critical", "high", "medium", "low")


def render_markdown_report(report: AuditReport, *, repository_path: Path) -> str:
    """Render active findings as a Markdown brief a coding agent can act on."""
    findings = unsuppressed_findings(report.findings)
    by_severity: dict[str, list[Finding]] = {level: [] for level in _SEVERITY_ORDER}
    for finding in findings:
        by_severity.setdefault(str(finding.severity), []).append(finding)

    lines: list[str] = [
        "# AgentHarness findings",
        "",
        f"Repository: `{repository_path}`",
        f"Findings: {len(findings)} active "
        + ", ".join(
            f"{len(by_severity[level])} {level}"
            for level in _SEVERITY_ORDER
            if by_severity.get(level)
        ),
        "",
        "Each finding below names a file and line, why it matters, and what to change. Work "
        "through them highest severity first. Confirm each site before editing: these come from "
        "static analysis and some may be intentional.",
        "",
    ]

    if not findings:
        lines.append("No active findings. Nothing to fix.")
        return "\n".join(lines) + "\n"

    for level in _SEVERITY_ORDER:
        group = by_severity.get(level) or []
        if not group:
            continue
        lines.append(f"## {level.capitalize()} ({len(group)})")
        lines.append("")
        for finding in group:
            lines.append(f"### {finding.title}")
            lines.append("")
            lines.append(f"`{finding.rule_id}` · confidence {finding.confidence:.2f}")
            lines.append("")
            lines.append("Locations:")
            lines.append("")
            for item in finding.evidence:
                location = item.path if item.line is None else f"{item.path}:{item.line}"
                suffix = f" — `{item.symbol}`" if item.symbol else ""
                lines.append(f"- `{location}`{suffix}")
            lines.append("")
            lines.append(f"**What it is:** {finding.description}")
            lines.append("")
            lines.append(f"**Why it matters:** {finding.impact}")
            lines.append("")
            lines.append(f"**What to change:** {finding.remediation}")
            lines.append("")
    return "\n".join(lines) + "\n"


def write_markdown_report(path: Path, report: AuditReport, *, repository_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_markdown_report(report, repository_path=repository_path), encoding="utf-8"
    )
