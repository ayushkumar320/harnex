"""Scan report assembly, canonical JSON, and human rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.table import Table

from autoharness.scan_models import (
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
    return AuditReport(
        repository=inventory,
        facts=facts,
        parse_failures=[],
        summary=summary,
        next_action="Review the JSON report, then run Phase 2 work when provider routing is ready.",
    )


def attach_parse_failures(report: AuditReport, parse_failures: list[ParseFailure]) -> AuditReport:
    return report.model_copy(update={"parse_failures": parse_failures})


def canonical_json(report: AuditReport) -> str:
    payload = report.model_dump(mode="json", exclude_none=True, by_alias=False)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_report(path: Path, report: AuditReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(report) + "\n", encoding="utf-8")


def render_human_summary(console: Console, report: AuditReport, *, artifact_path: Path) -> None:
    summary = report.summary
    console.print("AutoHarness scan is read-only: target code was parsed as data, not executed.")
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
    if report.evidence_bundle is not None:
        table.add_row("Local evidence chunks", str(len(report.evidence_bundle.local_evidence)))
        table.add_row(
            "External evidence chunks",
            str(len(report.evidence_bundle.external_evidence)),
        )
    console.print(table)
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
