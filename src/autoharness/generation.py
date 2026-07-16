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

GENERATOR_VERSION = "phase5.generator.v1"
TEMPLATE_VERSION = "phase5.direct_provider_runtime_templates.v1"

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
    status: Literal["staged", "applied"]
    mode: Literal["dry_run", "apply"]
    plan_hash: str
    plan_path: str
    repository_root: str
    staging_root: str
    files: list[GeneratedFileManifest]
    transaction_id: str | None = None
    journal_path: str | None = None
    next_action: str


class TransactionFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    previous_hash: str | None = None
    previous_backup_path: str | None = None
    generated_base_path: str | None = None
    new_hash: str


class ApplyTransactionJournal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["apply_transaction_journal"] = "apply_transaction_journal"
    transaction_id: str
    status: Literal["applied", "rolled_back"]
    plan_hash: str
    repository_root: str
    files: list[TransactionFile]


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


def load_transaction_journal(path: Path) -> ApplyTransactionJournal:
    try:
        return ApplyTransactionJournal.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise AutoHarnessError(
            code="AH-G011",
            message="Existing transaction journal is not compatible.",
            context=ErrorContext(
                field="journal",
                source="transaction journal",
                expected="A readable AutoHarness apply_transaction_journal artifact.",
                next_action="Review the existing generated files before reapplying.",
            ),
            exit_code=4,
        ) from exc


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


def apply_approved_plan(
    *,
    plan_path: Path,
    output_path: Path,
    confirm: bool,
) -> ApplyPreview:
    if not confirm:
        raise AutoHarnessError(
            code="AH-G007",
            message="Apply requires explicit approval.",
            context=ErrorContext(
                field="yes",
                source="flag",
                expected="--yes",
                next_action="Run with --dry-run first, then pass --yes to apply staged files.",
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
    transaction_id = _hash_suffix(plan_hash)
    journal_path = repository_root / ".autoharness" / "transactions" / f"{transaction_id}.json"
    journal = _apply_staged_files(
        manifests,
        repository_root=repository_root,
        plan_hash=plan_hash,
        transaction_id=transaction_id,
        journal_path=journal_path,
    )
    preview = ApplyPreview(
        status="applied",
        mode="apply",
        plan_hash=plan_hash,
        plan_path=str(plan_path),
        repository_root=str(repository_root),
        staging_root=str(staging_root),
        files=manifests,
        transaction_id=journal.transaction_id,
        journal_path=str(journal_path),
        next_action="Review the applied files. Use the transaction journal as the rollback record.",
    )
    write_apply_preview(output_path, preview)
    return preview


def canonical_apply_preview_json(preview: ApplyPreview) -> str:
    payload = preview.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_apply_preview(path: Path, preview: ApplyPreview) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_apply_preview_json(preview) + "\n", encoding="utf-8")


def canonical_transaction_json(journal: ApplyTransactionJournal) -> str:
    payload = journal.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_transaction_journal(path: Path, journal: ApplyTransactionJournal) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_transaction_json(journal) + "\n", encoding="utf-8")


def render_apply_preview(console: Console, preview: ApplyPreview, *, artifact_path: Path) -> None:
    if preview.mode == "dry_run":
        console.print(
            "AutoHarness apply dry-run: staged files were written under .autoharness only."
        )
    else:
        console.print("AutoHarness apply completed with a transaction journal.")
    console.print(f"Status: {preview.status}")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Files staged", str(len(preview.files)))
    table.add_row("Mode", preview.mode)
    console.print(table)
    for item in preview.files:
        console.print(f"- {item.path} -> {item.staged_path}")
    if preview.journal_path is not None:
        console.print(f"Transaction journal: {preview.journal_path}")
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
            if target_path.exists() and not target_path.is_file():
                raise _path_error(rel_path)
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


def _apply_staged_files(
    manifests: list[GeneratedFileManifest],
    *,
    repository_root: Path,
    plan_hash: str,
    transaction_id: str,
    journal_path: Path,
) -> ApplyTransactionJournal:
    files: list[TransactionFile] = []
    applied: list[tuple[Path, Path | None]] = []
    previous_journal = _load_existing_journal(journal_path)
    try:
        for manifest in manifests:
            target = _target_path(repository_root, manifest.path)
            staged = Path(manifest.staged_path)
            if not staged.is_file():
                raise AutoHarnessError(
                    code="AH-G008",
                    message="Staged generated file is missing.",
                    context=ErrorContext(
                        field="staged_path",
                        source="apply preview",
                        expected="An existing staged file.",
                        next_action="Run harness apply again to regenerate the staging area.",
                    ),
                    exit_code=4,
                    details={"staged_path": str(staged)},
                )
            previous_hash: str | None = None
            previous_backup_path: str | None = None
            generated_base_path = _generated_base_path(journal_path, manifest.path)
            if target.exists():
                if not target.is_file():
                    raise _path_error(manifest.path)
                previous_entry = (
                    _journal_file(previous_journal, manifest.path)
                    if previous_journal is not None
                    else None
                )
                data = _merge_reapply_content(
                    manifest=manifest,
                    current_path=target,
                    staged_path=staged,
                    previous_entry=previous_entry,
                )
                previous_hash = _sha256_bytes(target.read_bytes())
            else:
                data = staged.read_bytes()
            target.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(target, data)
            generated_base_path.parent.mkdir(parents=True, exist_ok=True)
            generated_base_path.write_bytes(staged.read_bytes())
            applied.append((target, None))
            files.append(
                TransactionFile(
                    path=manifest.path,
                    previous_hash=previous_hash,
                    previous_backup_path=previous_backup_path,
                    generated_base_path=str(generated_base_path),
                    new_hash=manifest.content_hash,
                )
            )
        journal = ApplyTransactionJournal(
            transaction_id=transaction_id,
            status="applied",
            plan_hash=plan_hash,
            repository_root=str(repository_root),
            files=files,
        )
        write_transaction_journal(journal_path, journal)
        return journal
    except AutoHarnessError:
        _rollback_applied(applied)
        rolled_back = ApplyTransactionJournal(
            transaction_id=transaction_id,
            status="rolled_back",
            plan_hash=plan_hash,
            repository_root=str(repository_root),
            files=files,
        )
        write_transaction_journal(journal_path, rolled_back)
        raise
    except Exception as exc:
        _rollback_applied(applied)
        rolled_back = ApplyTransactionJournal(
            transaction_id=transaction_id,
            status="rolled_back",
            plan_hash=plan_hash,
            repository_root=str(repository_root),
            files=files,
        )
        write_transaction_journal(journal_path, rolled_back)
        raise AutoHarnessError(
            code="AH-G009",
            message="Apply failed and previously written files were rolled back.",
            context=ErrorContext(
                field="files",
                source="apply transaction",
                expected="All generated files can be written atomically.",
                next_action=(
                    "Inspect the transaction journal and retry after resolving the write failure."
                ),
            ),
            exit_code=5,
            details={"transaction_id": transaction_id, "cause": str(exc)},
        ) from exc


def _atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(f".{path.name}.autoharness-tmp")
    temp.write_bytes(data)
    temp.replace(path)


def _rollback_applied(applied: list[tuple[Path, Path | None]]) -> None:
    for target, backup in reversed(applied):
        if backup is None:
            if target.exists():
                target.unlink()
            continue
        _atomic_write(target, backup.read_bytes())


def _load_existing_journal(path: Path) -> ApplyTransactionJournal | None:
    if not path.exists():
        return None
    journal = load_transaction_journal(path)
    if journal.status != "applied":
        return None
    return journal


def _journal_file(
    journal: ApplyTransactionJournal | None,
    rel_path: str,
) -> TransactionFile | None:
    if journal is None:
        return None
    for item in journal.files:
        if item.path == rel_path:
            return item
    return None


def _merge_reapply_content(
    *,
    manifest: GeneratedFileManifest,
    current_path: Path,
    staged_path: Path,
    previous_entry: TransactionFile | None,
) -> bytes:
    if previous_entry is None or previous_entry.generated_base_path is None:
        raise _reapply_conflict(manifest.path, "No prior generated base is available.")
    base_path = Path(previous_entry.generated_base_path)
    if not base_path.is_file():
        raise _reapply_conflict(manifest.path, "Prior generated base snapshot is missing.")
    current = current_path.read_bytes()
    base = base_path.read_bytes()
    new = staged_path.read_bytes()
    current_hash = _sha256_bytes(current)
    if current_hash == manifest.content_hash:
        return current
    if current_hash == previous_entry.new_hash:
        return new
    if current.startswith(base):
        suffix = current[len(base) :]
        if not _looks_generated_conflict_suffix(suffix):
            return new + suffix
    raise _reapply_conflict(
        manifest.path,
        "Current file has edits inside the generated base region.",
    )


def _looks_generated_conflict_suffix(suffix: bytes) -> bool:
    return b"<<<<<<<" in suffix or b"=======" in suffix or b">>>>>>>" in suffix


def _reapply_conflict(path: str, reason: str) -> AutoHarnessError:
    return AutoHarnessError(
        code="AH-G010",
        message="Generated target has unmergeable local edits.",
        context=ErrorContext(
            field="files",
            source="target repository",
            expected="Unchanged generated base or append-only user edits.",
            next_action="Review the existing generated file and resolve the conflict manually.",
        ),
        exit_code=4,
        details={"path": path, "reason": reason},
    )


def _generated_base_path(journal_path: Path, rel_path: str) -> Path:
    return journal_path.parent / journal_path.stem / "generated-base" / rel_path


def _render_templates(action: PlanAction) -> dict[str, str]:
    finding_ids = ", ".join(repr(item) for item in sorted(action.finding_ids))
    verification = "\n".join(f"# - {item}" for item in action.verification)
    return {
        ".autoharness/generated/autoharness_config.py": (
            '"""Generated AutoHarness runtime configuration.\n\n'
            "This file is staged for review and does not grant external permissions.\n"
            '"""\n\n'
            f"FINDING_IDS = [{finding_ids}]\n"
            f'ADAPTER = "{action.adapter}"\n'
            'GENERATION_STATE = "runtime_review"\n'
            'DEFAULT_RUNTIME_LOG_PATH = ".autoharness/runtime/runtime.jsonl"\n'
            "DEFAULT_RETRY_POLICY = {\n"
            "    'max_attempts': 3,\n"
            "    'total_elapsed_budget_seconds': 10.0,\n"
            "    'base_delay_seconds': 0.1,\n"
            "    'max_delay_seconds': 2.0,\n"
            "    'jitter_seconds': 0.0,\n"
            "}\n"
        ),
        ".autoharness/generated/autoharness_jsonl_logger.py": (
            '"""Generated JSONL logging helpers for AutoHarness runtime evidence."""\n\n'
            "from __future__ import annotations\n\n"
            "import json\n"
            "from pathlib import Path\n\n\n"
            "from autoharness.runtime import RuntimeEvent, RuntimeJsonlWriter, "
            "redact_runtime_payload\n\n\n"
            "def write_event(path: Path, event: RuntimeEvent) -> bool:\n"
            "    return RuntimeJsonlWriter(path).write_event(event)\n\n\n"
            "def read_events(path: Path) -> list[dict[str, object]]:\n"
            "    if not path.exists():\n"
            "        return []\n"
            "    lines = path.read_text(encoding='utf-8').splitlines()\n"
            "    return [json.loads(line) for line in lines]\n\n\n"
            "def redacted_event_payload(event: RuntimeEvent) -> dict[str, object]:\n"
            "    payload = redact_runtime_payload(event.model_dump(mode='json'))\n"
            "    if not isinstance(payload, dict):\n"
            "        return {}\n"
            "    return payload\n"
        ),
        ".autoharness/generated/autoharness_runner.py": (
            '"""Generated direct-provider runtime wrapper.\n\n'
            "This wrapper uses fake-provider-friendly runtime controls. It does not execute\n"
            "the target repository or prove sandbox enforcement.\n"
            '"""\n\n'
            "from __future__ import annotations\n\n"
            "import time\n"
            "from collections.abc import Callable, Mapping\n"
            "from pathlib import Path\n"
            "from typing import Any\n\n"
            "from autoharness.runtime import (\n"
            "    Clock,\n"
            "    RuntimeEvent,\n"
            "    RuntimeEventType,\n"
            "    RuntimeFailure,\n"
            "    RuntimeFailureKind,\n"
            "    RuntimeJsonlWriter,\n"
            "    RuntimeRetryExecutor,\n"
            "    RuntimeStatus,\n"
            "    RetryPolicy,\n"
            "    SideEffectClassification,\n"
            "    build_failure_context_packet,\n"
            "    summarize_runtime_failure,\n"
            ")\n\n"
            "from autoharness_config import (\n"
            "    ADAPTER,\n"
            "    DEFAULT_RETRY_POLICY,\n"
            "    DEFAULT_RUNTIME_LOG_PATH,\n"
            "    FINDING_IDS,\n"
            ")\n\n"
            "ProviderCall = Callable[[int], Mapping[str, Any]]\n\n\n"
            "def describe_generated_harness() -> dict[str, object]:\n"
            "    return {\n"
            "        'adapter': ADAPTER,\n"
            "        'finding_ids': list(FINDING_IDS),\n"
            "        'status': 'runtime_review',\n"
            "    }\n\n\n"
            "def run_direct_provider(\n"
            "    provider_call: ProviderCall,\n"
            "    *,\n"
            "    user_goal: str = 'Run the audited direct provider call.',\n"
            "    run_id: str = 'autoharness-run',\n"
            "    operation_id: str = 'direct-provider-call',\n"
            "    log_path: Path | str = DEFAULT_RUNTIME_LOG_PATH,\n"
            "    clock: Clock | None = None,\n"
            "    random_source: object | None = None,\n"
            ") -> dict[str, object]:\n"
            "    evidence_path = Path(log_path)\n"
            "    writer = RuntimeJsonlWriter(evidence_path)\n"
            "    writer.write_event(\n"
            "        RuntimeEvent(\n"
            "            event_type=RuntimeEventType.RUN_STARTED,\n"
            "            run_id=run_id,\n"
            "            timestamp_ms=_now_ms(clock),\n"
            "            status=RuntimeStatus.STARTED,\n"
            "            fields={'adapter': ADAPTER, 'finding_ids': list(FINDING_IDS)},\n"
            "        )\n"
            "    )\n"
            "    executor = RuntimeRetryExecutor(\n"
            "        RetryPolicy(**DEFAULT_RETRY_POLICY),\n"
            "        clock=clock,\n"
            "        random_source=random_source,\n"
            "    )\n"
            "    outcome = executor.run(\n"
            "        operation_id=operation_id,\n"
            "        side_effect_classification=SideEffectClassification.READ_ONLY,\n"
            "        operation=lambda attempt: _call_provider(provider_call, attempt),\n"
            "    )\n"
            "    _write_ledger_events(writer, run_id, outcome.ledger.entries)\n"
            "    summary = summarize_runtime_failure(\n"
            "        outcome=outcome,\n"
            "        side_effect_classification=SideEffectClassification.READ_ONLY,\n"
            "        evidence_artifact=evidence_path,\n"
            "    )\n"
            "    correction_packet = build_failure_context_packet(\n"
            "        outcome=outcome,\n"
            "        operation_id=operation_id,\n"
            "        user_goal=user_goal,\n"
            "        side_effect_classification=SideEffectClassification.READ_ONLY,\n"
            "    )\n"
            "    writer.write_event(\n"
            "        RuntimeEvent(\n"
            "            event_type=RuntimeEventType.RUN_FINISHED,\n"
            "            run_id=run_id,\n"
            "            operation_id=operation_id,\n"
            "            timestamp_ms=_now_ms(clock),\n"
            "            duration_ms=summary.elapsed_ms,\n"
            "            status=outcome.status,\n"
            "            failure_kind=outcome.failure_kind,\n"
            "            fields={'evidence_artifact': str(evidence_path)},\n"
            "        )\n"
            "    )\n"
            "    return {\n"
            "        'adapter': ADAPTER,\n"
            "        'status': outcome.status.value,\n"
            "        'attempts': outcome.attempts,\n"
            "        'result': outcome.result,\n"
            "        'summary': summary.model_dump(mode='json', exclude_none=True),\n"
            "        'correction_packet': (\n"
            "            correction_packet.model_dump(mode='json', exclude_none=True)\n"
            "            if correction_packet is not None\n"
            "            else None\n"
            "        ),\n"
            "        'ledger': [entry.model_dump(mode='json', exclude_none=True) "
            "for entry in outcome.ledger.entries],\n"
            "    }\n\n\n"
            "def _call_provider(provider_call: ProviderCall, attempt: int) -> Mapping[str, Any]:\n"
            "    try:\n"
            "        return provider_call(attempt)\n"
            "    except RuntimeFailure:\n"
            "        raise\n"
            "    except Exception as exc:\n"
            "        raise RuntimeFailure(RuntimeFailureKind.TOOL_FAILURE, str(exc)) from exc\n\n\n"
            "def _write_ledger_events(\n"
            "    writer: RuntimeJsonlWriter,\n"
            "    run_id: str,\n"
            "    entries: list[object],\n"
            ") -> None:\n"
            "    for entry in entries:\n"
            "        event_type = (\n"
            "            RuntimeEventType.MODEL_CALL_STARTED\n"
            "            if entry.phase == 'started'\n"
            "            else RuntimeEventType.MODEL_CALL_FINISHED\n"
            "        )\n"
            "        if entry.status == RuntimeStatus.RETRY_SCHEDULED:\n"
            "            event_type = RuntimeEventType.RETRY_SCHEDULED\n"
            "        writer.write_event(\n"
            "            RuntimeEvent(\n"
            "                event_type=event_type,\n"
            "                run_id=run_id,\n"
            "                operation_id=entry.operation_id,\n"
            "                attempt=entry.attempt,\n"
            "                timestamp_ms=entry.timestamp_ms,\n"
            "                status=entry.status,\n"
            "                failure_kind=entry.failure_kind,\n"
            "                fields={\n"
            "                    'side_effect_classification': "
            "entry.side_effect_classification.value,\n"
            "                },\n"
            "            )\n"
            "        )\n\n\n"
            "def _now_ms(clock: Clock | None) -> int:\n"
            "    if clock is not None:\n"
            "        return int(clock.monotonic() * 1000)\n"
            "    return int(time.monotonic() * 1000)\n"
        ),
        ".autoharness/generated/tests/test_autoharness_smoke.py": (
            '"""Generated smoke tests for the staged AutoHarness runtime wrapper."""\n\n'
            "from pathlib import Path\n\n"
            "from autoharness.runtime import RuntimeFailure, RuntimeFailureKind\n"
            "from autoharness_runner import describe_generated_harness, run_direct_provider\n\n\n"
            "class FakeClock:\n"
            "    def __init__(self) -> None:\n"
            "        self.now = 0.0\n"
            "        self.sleeps: list[float] = []\n\n"
            "    def monotonic(self) -> float:\n"
            "        return self.now\n\n"
            "    def sleep(self, seconds: float) -> None:\n"
            "        self.sleeps.append(seconds)\n"
            "        self.now += seconds\n\n\n"
            "def test_generated_harness_describes_runtime_review_state() -> None:\n"
            "    description = describe_generated_harness()\n"
            "    assert description['status'] == 'runtime_review'\n\n\n"
            "def test_generated_runtime_retries_read_only_provider(tmp_path: Path) -> None:\n"
            "    clock = FakeClock()\n"
            "    calls = 0\n\n"
            "    def provider(attempt: int) -> dict[str, object]:\n"
            "        nonlocal calls\n"
            "        calls += 1\n"
            "        if attempt == 1:\n"
            "            raise RuntimeFailure(\n"
            "                RuntimeFailureKind.RATE_LIMITED,\n"
            "                'rate limited',\n"
            "                retry_after_seconds=0.2,\n"
            "            )\n"
            "        return {'content': 'ok'}\n\n"
            "    result = run_direct_provider(\n"
            "        provider,\n"
            "        log_path=tmp_path / 'runtime.jsonl',\n"
            "        clock=clock,\n"
            "    )\n\n"
            "    assert result['status'] == 'success'\n"
            "    assert result['attempts'] == 2\n"
            "    assert calls == 2\n"
            "    assert clock.sleeps == [0.2]\n\n\n"
            "def test_generated_runtime_emits_correction_packet(tmp_path: Path) -> None:\n"
            "    def provider(_: int) -> dict[str, object]:\n"
            "        raise RuntimeFailure(\n"
            "            RuntimeFailureKind.MALFORMED_STRUCTURED_OUTPUT,\n"
            "            'bad json with sk-secret-token',\n"
            "        )\n\n"
            "    result = run_direct_provider(\n"
            "        provider,\n"
            "        user_goal='summarize without leaking token',\n"
            "        log_path=tmp_path / 'runtime.jsonl',\n"
            "        clock=FakeClock(),\n"
            "    )\n\n"
            "    assert result['status'] == 'retry_exhausted'\n"
            "    assert result['correction_packet']['failure_kind'] == "
            "'malformed_structured_output'\n"
            "    assert result['correction_packet']['safe_message'] == '[redacted]'\n"
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
