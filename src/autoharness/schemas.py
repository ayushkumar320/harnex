"""Versioned base schemas for persisted AutoHarness artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BaseArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CommandEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    command: str
    status: Literal["ok", "error"]
