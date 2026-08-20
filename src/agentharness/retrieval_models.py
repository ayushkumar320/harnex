"""Schemas for local and external evidence used by model assistance."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RetrievedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: Literal["local_documentation", "docstring", "external"]
    path: str
    heading_or_symbol: str | None = None
    start_line: int
    end_line: int
    content_hash: str
    text: str
    score: float


class ExternalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    canonical_url: str
    final_url: str
    title: str
    domain: str
    content_hash: str
    text: str
    query_hash: str
    relevance_score: float
    credits_used: int
    trust_label: Literal["official", "maintainer", "unverified"]


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    structural_fact_ids: list[str] = Field(default_factory=list)
    local_evidence: list[RetrievedEvidence] = Field(default_factory=list)
    external_evidence: list[ExternalEvidence] = Field(default_factory=list)
    incomplete_reason: str | None = None


class EvidenceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    manifest_hash: str
    data_policy: Literal["disabled", "local_only", "remote_allowed"]
    local_evidence_ids: list[str]
    external_evidence_ids: list[str]
    redaction_notes: list[str] = Field(default_factory=list)
