"""Workflow run artifacts shared by the one-command orchestration commands."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from rich.console import Console

StageStatus = Literal["completed", "failed", "declined", "skipped", "not_available"]
RunStatus = Literal["completed", "incomplete", "failed", "declined"]


class WorkflowStage(BaseModel):
    """One orchestrated stage of a workflow command."""

    name: str
    status: StageStatus
    duration_ms: int
    artifact: str | None = None
    detail: str | None = None


class WorkflowRun(BaseModel):
    """Canonical record of a one-command workflow invocation."""

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["workflow_run"] = "workflow_run"
    command: str
    status: RunStatus
    stages: list[WorkflowStage] = Field(default_factory=list)
    next_action: str


class WorkflowRecorder:
    """Collects stage results so a partial run still reports what completed."""

    def __init__(self, command: str) -> None:
        self.command = command
        self.stages: list[WorkflowStage] = []

    @contextmanager
    def stage(self, name: str) -> Iterator[dict[str, str | None]]:
        """Time one stage and record it, marking it failed if it raises."""
        started = time.monotonic()
        result: dict[str, str | None] = {"status": "completed", "artifact": None, "detail": None}
        try:
            yield result
        except BaseException:
            self._record(name, "failed", started, result)
            raise
        self._record(name, result["status"] or "completed", started, result)

    def _record(
        self,
        name: str,
        status: str,
        started: float,
        result: dict[str, str | None],
    ) -> None:
        self.stages.append(
            WorkflowStage(
                name=name,
                status=status,  # type: ignore[arg-type]
                duration_ms=int((time.monotonic() - started) * 1000),
                artifact=result["artifact"],
                detail=result["detail"],
            )
        )

    def build(self, *, next_action: str, status: RunStatus | None = None) -> WorkflowRun:
        if status is None:
            status = _derive_status(self.stages)
        return WorkflowRun(
            command=self.command,
            status=status,
            stages=list(self.stages),
            next_action=next_action,
        )


def _derive_status(stages: list[WorkflowStage]) -> RunStatus:
    statuses = {stage.status for stage in stages}
    if "failed" in statuses:
        return "failed"
    if "declined" in statuses:
        return "declined"
    if statuses & {"skipped", "not_available"}:
        return "incomplete"
    return "completed"


def canonical_workflow_json(run: WorkflowRun) -> str:
    return json.dumps(run.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def write_workflow_run(path: Path, run: WorkflowRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_workflow_json(run) + "\n", encoding="utf-8")


def render_workflow_summary(console: Console, run: WorkflowRun, *, artifact_path: Path) -> None:
    console.print(f"Workflow: {run.command}")
    console.print(f"Status: {run.status}")
    for stage in run.stages:
        line = f"  {stage.name}: {stage.status} ({stage.duration_ms} ms)"
        if stage.detail:
            line += f" - {stage.detail}"
        console.print(line)
        if stage.artifact:
            console.print(f"    artifact: {stage.artifact}")
    console.print(f"Next action: {run.next_action}")
    console.print(f"Workflow artifact: {artifact_path}")
