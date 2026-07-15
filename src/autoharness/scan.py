"""Phase 1 scan orchestration."""

from __future__ import annotations

from pathlib import Path

from autoharness.python_scanner import scan_python_files
from autoharness.reporter import attach_parse_failures, build_report
from autoharness.repository import DEFAULT_MAX_FILE_BYTES, build_inventory
from autoharness.scan_models import AuditReport


def scan_repository(root: Path, *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> AuditReport:
    inventory = build_inventory(root, max_file_bytes=max_file_bytes)
    facts, parse_failures = scan_python_files(Path(inventory.root), inventory.included_files)
    report = build_report(inventory=inventory, facts=facts, parse_failures=len(parse_failures))
    return attach_parse_failures(report, parse_failures)
