"""Deterministic Phase 3 finding catalog and rule engine."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from autoharness.scan_models import ExcludedPath, StructuralFact


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SupportTier(StrEnum):
    DETECTED = "detected"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


class GenerationState(StrEnum):
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


DETECTOR_VERSION = "phase3.findings.v1"


class FindingEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    id: str
    path: str
    line: int | None = None
    symbol: str | None = None
    detail: str | None = None


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    id: str
    rule_id: str
    title: str
    description: str
    impact: str
    severity: Severity
    support: SupportTier
    confidence: float
    confidence_factors: list[str]
    generation: GenerationState
    evidence: list[FindingEvidence]
    remediation: str
    next_action: str
    detector_version: str = DETECTOR_VERSION
    suppressed: bool = False
    suppression_reason: str | None = None
    suppression_expires: str | None = None


class Suppression(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    path: str | None = None
    reason: str
    expires: str | None = None


class CatalogRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    impact: str
    severity: Severity
    generation: GenerationState
    remediation: str
    next_action: str


CATALOG: dict[str, CatalogRule] = {
    "AH-R101": CatalogRule(
        title="Model call has no detected reliability instrumentation",
        description=(
            "A direct model-provider call was detected without verified harness controls."
        ),
        impact=(
            "Timeouts, rate limits, malformed responses, and token usage may be hard to classify."
        ),
        severity=Severity.HIGH,
        generation=GenerationState.REVIEW_REQUIRED,
        remediation="Add bounded provider routing, structured logging, and response validation.",
        next_action=(
            "Run harness plan on this scan artifact and review the instrumentation action."
        ),
    ),
    "AH-R102": CatalogRule(
        title="Broad exception handler can hide reliability failures",
        description="A broad Exception or bare except handler was detected.",
        impact="Provider, tool, or policy failures may be swallowed without recovery evidence.",
        severity=Severity.MEDIUM,
        generation=GenerationState.BLOCKED,
        remediation="Catch normalized failure classes and preserve structured error evidence.",
        next_action="Review the handler and narrow the caught exception types.",
    ),
    "AH-S101": CatalogRule(
        title="Tool side effect has no enforceable boundary",
        description="A shell, process, or filesystem write side effect was detected.",
        impact=(
            "Retries or verification could mutate external state without an enforcement boundary."
        ),
        severity=Severity.HIGH,
        generation=GenerationState.BLOCKED,
        remediation="Classify the side effect and run future verification in an enforced sandbox.",
        next_action="Review the side effect and document whether it is read-only or idempotent.",
    ),
    "AH-S201": CatalogRule(
        title="Secret-like path or content was excluded from scan",
        description="The repository view excluded a path or file content as secret-like.",
        impact=(
            "Secrets are protected from retrieval, but nearby logging or provider calls may "
            "need review."
        ),
        severity=Severity.MEDIUM,
        generation=GenerationState.BLOCKED,
        remediation="Keep secrets out of prompts, logs, fixtures, and generated artifacts.",
        next_action="Confirm secret paths are intentional and ignored by runtime logging.",
    ),
    "AH-U101": CatalogRule(
        title="Dynamic registration or lookup is unresolved",
        description=(
            "Dynamic import, lookup, or registration prevents complete static interpretation."
        ),
        impact="AutoHarness may miss providers, tools, or entry points hidden behind lookup.",
        severity=Severity.LOW,
        generation=GenerationState.BLOCKED,
        remediation="Add explicit adapter annotations or simplify dynamic registration paths.",
        next_action="Review the dynamic site and decide whether an adapter annotation is needed.",
    ),
}


def derive_findings(
    facts: list[StructuralFact],
    exclusions: list[ExcludedPath],
    *,
    suppressions: list[Suppression] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    for fact in facts:
        if fact.kind == "model_call_candidate":
            findings.append(
                _from_fact(
                    "AH-R101",
                    fact,
                    ["deterministic_ast_match", "known_provider_symbol"],
                )
            )
        elif fact.kind == "broad_exception_handler":
            findings.append(_from_fact("AH-R102", fact, ["deterministic_ast_match"]))
        elif fact.kind == "side_effect_candidate":
            findings.append(
                _from_fact("AH-S101", fact, ["deterministic_ast_match", "known_side_effect_symbol"])
            )
        elif fact.kind == "unknown_dynamic_pattern":
            findings.append(
                _from_fact("AH-U101", fact, ["deterministic_ast_match", "dynamic_lookup_detected"])
            )
    for exclusion in exclusions:
        if exclusion.reason in {"secret_path", "secret_content"}:
            findings.append(_from_exclusion("AH-S201", exclusion))
    findings = _apply_suppressions(findings, suppressions or [])
    return sorted(findings, key=lambda item: (_severity_rank(item.severity), item.id))


def finding_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {severity.value: 0 for severity in Severity}
    for finding in findings:
        counts[finding.severity.value] += 1
    return counts


def unsuppressed_findings(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if not finding.suppressed]


def load_suppressions(root: Path) -> list[Suppression]:
    path = root / ".autoharness" / "suppressions.yml"
    if not path.exists():
        return []
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = document.get("suppressions", [])
    if not isinstance(items, list):
        return []
    suppressions = []
    for item in items:
        if isinstance(item, dict) and item.get("reason"):
            suppressions.append(Suppression.model_validate(item))
    return suppressions


def _from_fact(rule_id: str, fact: StructuralFact, factors: list[str]) -> Finding:
    catalog = CATALOG[rule_id]
    return Finding(
        id=_finding_id(rule_id, fact.evidence_hash),
        rule_id=rule_id,
        title=catalog.title,
        description=catalog.description,
        impact=catalog.impact,
        severity=catalog.severity,
        support=SupportTier.DETECTED,
        confidence=_confidence(factors),
        confidence_factors=factors,
        generation=catalog.generation,
        evidence=[
            FindingEvidence(
                source="structural_fact",
                id=fact.evidence_hash,
                path=fact.path,
                line=fact.line,
                symbol=fact.symbol,
                detail=fact.detail,
            )
        ],
        remediation=catalog.remediation,
        next_action=catalog.next_action,
    )


def _from_exclusion(rule_id: str, exclusion: ExcludedPath) -> Finding:
    catalog = CATALOG[rule_id]
    evidence_id = _excluded_id(exclusion)
    return Finding(
        id=_finding_id(rule_id, evidence_id),
        rule_id=rule_id,
        title=catalog.title,
        description=catalog.description,
        impact=catalog.impact,
        severity=catalog.severity,
        support=SupportTier.DETECTED,
        confidence=_confidence(["secret_filter_match"]),
        confidence_factors=["secret_filter_match"],
        generation=catalog.generation,
        evidence=[
            FindingEvidence(
                source="repository_exclusion",
                id=evidence_id,
                path=exclusion.path,
                detail=exclusion.reason,
            )
        ],
        remediation=catalog.remediation,
        next_action=catalog.next_action,
    )


def _finding_id(rule_id: str, evidence_id: str) -> str:
    digest = hashlib.sha256(f"{rule_id}|{evidence_id}".encode()).hexdigest()[:10]
    return f"{rule_id}-{digest}"


def _excluded_id(exclusion: ExcludedPath) -> str:
    digest = hashlib.sha256(f"{exclusion.path}|{exclusion.reason}".encode()).hexdigest()
    return "excluded:sha256:" + digest


def _confidence(factors: list[str]) -> float:
    score = 0.72 + (0.07 * min(len(factors), 3))
    return round(min(score, 0.93), 2)


def _severity_rank(severity: Severity) -> int:
    return {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }[severity]


def _apply_suppressions(findings: list[Finding], suppressions: list[Suppression]) -> list[Finding]:
    if not suppressions:
        return findings
    updated = []
    for finding in findings:
        suppression = _matching_suppression(finding, suppressions)
        if suppression is None:
            updated.append(finding)
            continue
        updated.append(
            finding.model_copy(
                update={
                    "suppressed": True,
                    "suppression_reason": suppression.reason,
                    "suppression_expires": suppression.expires,
                }
            )
        )
    return updated


def _matching_suppression(
    finding: Finding,
    suppressions: list[Suppression],
) -> Suppression | None:
    evidence_path = finding.evidence[0].path if finding.evidence else None
    for suppression in suppressions:
        if suppression.rule_id != finding.rule_id:
            continue
        if suppression.path is not None and suppression.path != evidence_path:
            continue
        return suppression
    return None
