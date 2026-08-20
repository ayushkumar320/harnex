"""Versioned schemas for Phase 1 scan artifacts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agentharness.findings import Finding
from agentharness.retrieval_models import EvidenceBundle


class ScanConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_file_bytes: int
    ignore_file: str


class IncludedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    language: str
    size_bytes: int
    content_hash: str


class ExcludedPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    reason: str


class RepositoryInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str
    included_files: list[IncludedFile]
    excluded_paths: list[ExcludedPath]
    language_counts: dict[str, int]
    scan_config: ScanConfig


class StructuralFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    path: str
    detector_id: str
    evidence_hash: str
    confidence_basis: str
    line: int | None = None
    column: int | None = None
    symbol: str | None = None
    detail: str | None = None
    adapter_candidates: list[str] = Field(default_factory=list)


class ParseFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    reason: str
    line: int | None = None
    column: int | None = None


class ScanSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["complete", "partial", "empty", "unsupported"]
    included_files: int
    excluded_paths: int
    python_files: int
    parse_failures: int
    total_facts: int
    functions: int
    cli_candidates: int
    model_call_candidates: int
    side_effect_candidates: int
    unknown_dynamic_patterns: int
    findings_total: int = 0
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    suppressed_findings: int = 0


class ArtifactFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_hash: str
    scan_config_hash: str
    detector_versions: dict[str, str]


class AuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["audit_report"] = "audit_report"
    repository: RepositoryInventory
    fingerprint: ArtifactFingerprint
    facts: list[StructuralFact]
    parse_failures: list[ParseFailure]
    findings: list[Finding] = Field(default_factory=list)
    evidence_bundle: EvidenceBundle | None = None
    summary: ScanSummary
    next_action: str
