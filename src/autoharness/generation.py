"""Phase 4 constrained generation preview pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from rich.console import Console
from rich.table import Table

from autoharness.errors import AutoHarnessError, ErrorContext
from autoharness.planning import HarnessPlan, PlanAction, load_scan_report

GENERATOR_VERSION = "phase4.generator.v1"
TEMPLATE_VERSION = "phase4.direct_provider_templates.v1"

SUPPORTED_ADAPTER = "openai_compatible"
SUPPORTED_OUTPUT_FILES = (
    ".autoharness/generated/autoharness_config.py",
    ".autoharness/generated/autoharness_jsonl_logger.py",
    ".autoharness/generated/autoharness_runner.py",
    ".autoharness/generated/tests/test_autoharness_smoke.py",
)


class GeneratedFileManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    staged_path: str
    generator_version: str
    template_version: str
    plan_hash: str
    base_hash: str | None = None
    content_hash: str
    action_id: str


class ApplyPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["apply_preview"] = "apply_preview"
    status: Literal["staged"]
    mode: Literal["dry_run"]
    plan_hash: str
    plan_path: str
    repository_root: str
    staging_root: str
    files: list[GeneratedFileManifest]
    next_action: str


def load_plan_artifact(path: Path) -> tuple[HarnessPlan, str]:
    try:
        raw = path.read_text(encoding="utf-8")
        plan = HarnessPlan.model_validate_json(raw)
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise AutoHarnessError(
            code="AH-G001",
            message="Apply input is not a compatible plan artifact.",
            context=ErrorContext(
                field="plan",
                source="argument",
                expected="A completed AutoHarness harness_plan JSON artifact.",
                next_action="Run harness plan first and pass its JSON output to harness apply.",
            ),
            exit_code=4,
        ) from exc
    return plan, _sha256_text(raw)


def stage_apply_preview(
    *,
    plan_path: Path,
    output_path: Path,
    dry_run: bool,
) -> ApplyPreview:
    if not dry_run:
        raise AutoHarnessError(
            code="AH-G002",
            message="Apply requires --dry-run in this Phase 4 slice.",
            context=ErrorContext(
                field="dry_run",
                source="flag",
                expected="--dry-run",
                next_action="Preview staged generation before enabling target writes.",
            ),
            exit_code=4,
        )
    plan, plan_hash = load_plan_artifact(plan_path)
    repository_root = _validate_plan_source(plan)
    actions = _approved_generation_actions(plan)
    staging_root = repository_root / ".autoharness" / "staging" / _hash_suffix(plan_hash)
    manifests = _stage_actions(
        actions,
        repository_root=repository_root,
        staging_root=staging_root,
        plan_hash=plan_hash,
    )
    preview = ApplyPreview(
        status="staged",
        mode="dry_run",
        plan_hash=plan_hash,
        plan_path=str(plan_path),
        repository_root=str(repository_root),
        staging_root=str(staging_root),
        files=manifests,
        next_action="Review the staged files and preview artifact before applying changes.",
    )
    write_apply_preview(output_path, preview)
    return preview


def canonical_apply_preview_json(preview: ApplyPreview) -> str:
    payload = preview.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_apply_preview(path: Path, preview: ApplyPreview) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_apply_preview_json(preview) + "\n", encoding="utf-8")


def render_apply_preview(console: Console, preview: ApplyPreview, *, artifact_path: Path) -> None:
    console.print("AutoHarness apply dry-run: staged files were written under .autoharness only.")
    console.print(f"Status: {preview.status}")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Files staged", str(len(preview.files)))
    table.add_row("Mode", preview.mode)
    console.print(table)
    for item in preview.files:
        console.print(f"- {item.path} -> {item.staged_path}")
    console.print(f"Detailed JSON: {artifact_path}")
    console.print(f"Next: {preview.next_action}")


def _validate_plan_source(plan: HarnessPlan) -> Path:
    scan_path = Path(plan.source_scan_path)
    report, scan_hash = load_scan_report(scan_path)
    if scan_hash != plan.source_scan_hash:
        raise AutoHarnessError(
            code="AH-G003",
            message="Plan source scan hash does not match the referenced scan artifact.",
            context=ErrorContext(
                field="source_scan_hash",
                source="plan artifact",
                expected="Hash of the current referenced scan artifact.",
                next_action="Run harness scan and harness plan again before apply.",
            ),
            exit_code=4,
        )
    # Reuse Phase 3 freshness checks by attempting to rebuild a compatible plan.
    from autoharness.planning import build_plan

    build_plan(report, scan_hash=scan_hash, scan_path=scan_path)
    return Path(report.repository.root)


def _approved_generation_actions(plan: HarnessPlan) -> list[PlanAction]:
    actions: list[PlanAction] = []
    for action in plan.actions:
        issues = _action_issues(action)
        if issues:
            raise AutoHarnessError(
                code="AH-G004",
                message="Plan contains an action that is not approved for Phase 4 generation.",
                context=ErrorContext(
                    field="actions",
                    source="plan artifact",
                    expected="Approved write_generated_files action for openai_compatible.",
                    next_action="Review and approve a compatible generation plan before apply.",
                ),
                exit_code=4,
                details={"action_id": action.id, "issues": issues},
            )
        actions.append(action)
    if not actions:
        raise AutoHarnessError(
            code="AH-G005",
            message="Plan contains no approved generation actions.",
            context=ErrorContext(
                field="actions",
                source="plan artifact",
                expected="At least one approved generation action.",
                next_action="Approve a compatible action before running harness apply.",
            ),
            exit_code=4,
        )
    return actions


def _action_issues(action: PlanAction) -> list[str]:
    issues: list[str] = []
    if action.permission != "write_generated_files":
        issues.append("permission must be write_generated_files")
    if action.approval_state != "approved":
        issues.append("approval_state must be approved")
    if action.adapter != SUPPORTED_ADAPTER:
        issues.append(f"adapter must be {SUPPORTED_ADAPTER}")
    if action.side_effect_classification != "read_only":
        issues.append("side_effect_classification must be read_only")
    if tuple(sorted(action.files)) != SUPPORTED_OUTPUT_FILES:
        issues.append("files must match the Phase 4 direct-provider template set")
    for path in action.files:
        if _unsafe_output_path(path):
            issues.append(f"unsafe output path: {path}")
    return issues


def _stage_actions(
    actions: list[PlanAction],
    *,
    repository_root: Path,
    staging_root: Path,
    plan_hash: str,
) -> list[GeneratedFileManifest]:
    manifests: list[GeneratedFileManifest] = []
    for action in sorted(actions, key=lambda item: item.id):
        for rel_path, content in _render_templates(action).items():
            target_path = _target_path(repository_root, rel_path)
            base_hash = _sha256_bytes(target_path.read_bytes()) if target_path.exists() else None
            staged_path = _staged_path(staging_root, rel_path)
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            encoded = content.encode("utf-8")
            staged_path.write_bytes(encoded)
            manifests.append(
                GeneratedFileManifest(
                    path=rel_path,
                    staged_path=str(staged_path),
                    generator_version=GENERATOR_VERSION,
                    template_version=TEMPLATE_VERSION,
                    plan_hash=plan_hash,
                    base_hash=base_hash,
                    content_hash=_sha256_bytes(encoded),
                    action_id=action.id,
                )
            )
    manifests.sort(key=lambda item: item.path)
    return manifests


def _render_templates(action: PlanAction) -> dict[str, str]:
    finding_ids = ", ".join(repr(item) for item in sorted(action.finding_ids))
    verification = "\n".join(f"# - {item}" for item in action.verification)
    return {
        ".autoharness/generated/autoharness_config.py": (
            '"""Generated AutoHarness configuration skeleton.\n\n'
            "This file is staged for review and is not an enforcement boundary.\n"
            '"""\n\n'
            f"FINDING_IDS = [{finding_ids}]\n"
            f'ADAPTER = "{action.adapter}"\n'
            'GENERATION_STATE = "staged_review"\n'
        ),
        ".autoharness/generated/autoharness_jsonl_logger.py": (
            '"""Generated JSONL logging interface skeleton."""\n\n'
            "from __future__ import annotations\n\n"
            "import json\n"
            "from collections.abc import Mapping\n"
            "from pathlib import Path\n\n\n"
            "def write_event(path: Path, event: Mapping[str, object]) -> None:\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    with path.open('a', encoding='utf-8') as handle:\n"
            "        handle.write(json.dumps(dict(event), sort_keys=True) + '\\n')\n"
        ),
        ".autoharness/generated/autoharness_runner.py": (
            '"""Generated provider runner skeleton.\n\n'
            "Runtime retry behavior is introduced in a later phase.\n"
            '"""\n\n'
            "from __future__ import annotations\n\n"
            "from .autoharness_config import ADAPTER, FINDING_IDS\n\n\n"
            "def describe_generated_harness() -> dict[str, object]:\n"
            "    return {\n"
            "        'adapter': ADAPTER,\n"
            "        'finding_ids': list(FINDING_IDS),\n"
            "        'status': 'not_verified',\n"
            "    }\n"
        ),
        ".autoharness/generated/tests/test_autoharness_smoke.py": (
            '"""Generated smoke tests for the staged AutoHarness skeleton."""\n\n'
            "from autoharness_runner import describe_generated_harness\n\n\n"
            "def test_generated_harness_describes_review_state() -> None:\n"
            "    description = describe_generated_harness()\n"
            "    assert description['status'] == 'not_verified'\n"
            f"{verification}\n"
        ),
    }


def _target_path(repository_root: Path, rel_path: str) -> Path:
    if _unsafe_output_path(rel_path):
        raise _path_error(rel_path)
    _reject_existing_symlink_component(repository_root, rel_path)
    target = (repository_root / rel_path).resolve(strict=False)
    try:
        target.relative_to(repository_root)
    except ValueError as exc:
        raise _path_error(rel_path) from exc
    return target


def _staged_path(staging_root: Path, rel_path: str) -> Path:
    staged = (staging_root / rel_path).resolve(strict=False)
    try:
        staged.relative_to(staging_root)
    except ValueError as exc:
        raise _path_error(rel_path) from exc
    return staged


def _unsafe_output_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    return candidate.is_absolute() or ".." in candidate.parts


def _reject_existing_symlink_component(repository_root: Path, rel_path: str) -> None:
    current = repository_root
    for part in PurePosixPath(rel_path).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise _path_error(rel_path)


def _path_error(path: str) -> AutoHarnessError:
    return AutoHarnessError(
        code="AH-G006",
        message="Generated output path is outside the approved repository boundary.",
        context=ErrorContext(
            field="files",
            source="plan artifact",
            expected="Repository-relative paths without traversal or symlink escapes.",
            next_action="Regenerate or edit the plan to use approved relative output paths.",
        ),
        exit_code=4,
        details={"path": path},
    )


def _hash_suffix(value: str) -> str:
    return value.removeprefix("sha256:")[:12]


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()
