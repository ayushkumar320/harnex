"""Deterministic evidence citation validation for model-assisted outputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentharness.retrieval_models import EvidenceBundle


class CitedModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class CitationValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    missing_evidence_ids: list[str] = Field(default_factory=list)


def validate_citations(
    output: CitedModelOutput,
    bundle: EvidenceBundle,
) -> CitationValidationResult:
    valid_ids = set(bundle.structural_fact_ids)
    valid_ids.update(item.id for item in bundle.local_evidence)
    valid_ids.update(item.id for item in bundle.external_evidence)
    missing = sorted(
        {evidence_id for evidence_id in output.evidence_ids if evidence_id not in valid_ids}
    )
    return CitationValidationResult(valid=not missing, missing_evidence_ids=missing)
