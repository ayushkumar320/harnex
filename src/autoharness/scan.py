"""Phase 1 scan orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path

from autoharness.external_evidence import (
    ExternalEvidenceProvider,
    FileExternalEvidenceCache,
    WebEvidenceConfig,
    build_tavily_provider_from_env,
    collect_external_evidence,
    default_external_evidence_cache_root,
)
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
    web_evidence_config: WebEvidenceConfig | None = None,
    web_evidence_enabled: bool | None = None,
    external_provider: ExternalEvidenceProvider | None = None,
    external_cache: FileExternalEvidenceCache | None = None,
) -> AuditReport:
    inventory = build_inventory(root, max_file_bytes=max_file_bytes)
    facts, parse_failures = scan_python_files(Path(inventory.root), inventory.included_files)
    report = build_report(inventory=inventory, facts=facts, parse_failures=len(parse_failures))
    report = attach_parse_failures(report, parse_failures)
    if not online:
        return report
    if web_evidence_config is None:
        web_evidence_config = WebEvidenceConfig(enabled=bool(web_evidence_enabled))
    local_evidence = build_local_index(Path(inventory.root))
    provider = external_provider
    if provider is None and web_evidence_config.enabled:
        provider = build_tavily_provider_from_env()
    cache = external_cache
    if cache is None and web_evidence_config.enabled:
        cache = FileExternalEvidenceCache(
            default_external_evidence_cache_root(),
            ttl_days=web_evidence_config.cache_ttl_days,
        )
    external_evidence, incomplete_reason = asyncio.run(
        collect_external_evidence(
            local_texts=[item.text for item in local_evidence],
            config=web_evidence_config,
            provider=provider,
            cache=cache,
        )
    )
    bundle = EvidenceBundle(
        structural_fact_ids=[fact.evidence_hash for fact in facts],
        local_evidence=local_evidence,
        external_evidence=external_evidence,
        incomplete_reason=incomplete_reason,
    )
    return report.model_copy(update={"evidence_bundle": bundle})
