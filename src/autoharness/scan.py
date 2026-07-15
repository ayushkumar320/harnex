"""Phase 1 scan orchestration."""

from __future__ import annotations

from pathlib import Path

from autoharness.python_scanner import scan_python_files
from autoharness.reporter import attach_parse_failures, build_report
from autoharness.repository import DEFAULT_MAX_FILE_BYTES, build_inventory
from autoharness.retrieval import build_local_index
from autoharness.retrieval_models import EvidenceBundle
from autoharness.scan_models import AuditReport


def scan_repository(
    root: Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    online: bool = False,
    web_evidence_enabled: bool = False,
) -> AuditReport:
    inventory = build_inventory(root, max_file_bytes=max_file_bytes)
    facts, parse_failures = scan_python_files(Path(inventory.root), inventory.included_files)
    report = build_report(inventory=inventory, facts=facts, parse_failures=len(parse_failures))
    report = attach_parse_failures(report, parse_failures)
    if not online:
        return report
    local_evidence = build_local_index(Path(inventory.root))
    incomplete_reason = None if web_evidence_enabled else "web_evidence_disabled"
    bundle = EvidenceBundle(
        structural_fact_ids=[fact.evidence_hash for fact in facts],
        local_evidence=local_evidence,
        external_evidence=[],
        incomplete_reason=incomplete_reason,
    )
    return report.model_copy(update={"evidence_bundle": bundle})
