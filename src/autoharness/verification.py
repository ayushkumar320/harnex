"""Phase 7 deterministic verification reports."""

from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.table import Table

from autoharness.errors import AutoHarnessError, ErrorContext
from autoharness.reporter import fingerprint_for_inventory
from autoharness.runtime import (
    RetryPolicy,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeFailure,
    RuntimeFailureKind,
    RuntimeJsonlWriter,
    RuntimeRetryExecutor,
    RuntimeStatus,
    SideEffectClassification,
)
from autoharness.sandbox import (
    DockerSandboxBackend,
    SandboxBackendKind,
    SandboxCapabilityStatus,
    SandboxRequest,
    SandboxResources,
)
from autoharness.scan import scan_repository

VERIFY_SCHEMA_VERSION = "1.0"


type VerificationCheckStatus = Literal["passed", "failed", "not_exercised", "requires_approval"]
PASSED: VerificationCheckStatus = "passed"
FAILED: VerificationCheckStatus = "failed"
NOT_EXERCISED: VerificationCheckStatus = "not_exercised"
REQUIRES_APPROVAL: VerificationCheckStatus = "requires_approval"


class EvalDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["draft"] = "draft"
    source_path: str
    source_line: int
    source_hash: str
    candidate_task: str
    approval_required: str


class VerificationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: VerificationCheckStatus
    component: str
    evidence: list[str] = Field(default_factory=list)
    next_action: str
    duration_ms: int = 0


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["verification_report"] = "verification_report"
    repository_root: str
    disposable_workspace: str
    containment: dict[str, str | list[str]]
    checks: list[VerificationCheck]
    eval_drafts: list[EvalDraft]
    cleanup_status: Literal["removed", "retained"]
    summary: dict[str, int]
    next_action: str


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def verify_repository(
    repository_root: Path,
    *,
    sandbox_backend: DockerSandboxBackend | None = None,
    keep_workspace: bool = False,
) -> VerificationReport:
    root = _existing_directory(repository_root)
    before_hash = _tree_hash(root)
    workspace_parent = Path(tempfile.mkdtemp(prefix="autoharness-verify-"))
    workspace = workspace_parent / "workspace"
    cleanup_status: Literal["removed", "retained"] = "retained"
    checks: list[VerificationCheck] = []
    eval_drafts: list[EvalDraft] = []
    containment: dict[str, str | list[str]] = {
        "environment": "disposable workspace plus Docker sandbox when available",
        "network": "denied for sandbox checks",
        "credentials": "fixture credentials only",
        "source_write": "original working tree is hashed before and after verification",
        "requested_capabilities": [
            "read_only_source_mount",
            "approved_writable_mounts",
            "network_denied",
            "non_root_user",
            "resource_limits",
        ],
    }
    try:
        _copy_repository(root, workspace)
        checks.extend(
            [
                _check_scan_artifact_current(workspace),
                _check_generated_python_importable(workspace),
                _check_runtime_retry_and_redaction(workspace),
                _check_duplicate_side_effect_block(workspace),
                _check_sandbox_containment(workspace, sandbox_backend or DockerSandboxBackend()),
            ]
        )
        eval_drafts = _draft_evals(workspace)
        if eval_drafts:
            checks.append(
                VerificationCheck(
                    id="semantic_eval_drafts",
                    title="Semantic eval candidates require developer-approved oracles",
                    status=REQUIRES_APPROVAL,
                    component="evals",
                    evidence=[f"{len(eval_drafts)} draft eval candidate(s) created"],
                    next_action=(
                        "Review expected concepts, tool use, and external effects before scoring."
                    ),
                )
            )
        else:
            checks.append(
                VerificationCheck(
                    id="semantic_eval_drafts",
                    title="Semantic eval candidate discovery",
                    status=NOT_EXERCISED,
                    component="evals",
                    evidence=["No README examples or test descriptions were found."],
                    next_action="Add documented examples before generating draft semantic evals.",
                )
            )
        checks.append(_check_original_tree_unchanged(root, before_hash))
    finally:
        if keep_workspace:
            cleanup_status = "retained"
        else:
            shutil.rmtree(workspace_parent, ignore_errors=True)
            cleanup_status = "removed"

    report = VerificationReport(
        repository_root=str(root),
        disposable_workspace=str(workspace),
        containment=containment,
        checks=checks,
        eval_drafts=eval_drafts,
        cleanup_status=cleanup_status,
        summary=_summary(checks),
        next_action=_next_action(checks),
    )
    return report


def canonical_verification_json(report: VerificationReport) -> str:
    payload = report.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_verification_report(path: Path, report: VerificationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_verification_json(report) + "\n", encoding="utf-8")


def render_verification_summary(
    console: Console,
    report: VerificationReport,
    *,
    artifact_path: Path,
) -> None:
    console.print("AutoHarness verify uses fixture credentials and denied-network sandbox checks.")
    console.print(f"Repository: {report.repository_root}")
    console.print(f"Cleanup: {report.cleanup_status}")
    containment = report.containment
    console.print(f"Environment: {containment['environment']}")
    console.print(f"Network: {containment['network']}")
    console.print(f"Credentials: {containment['credentials']}")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Status")
    table.add_column("Count", justify="right")
    for status in ["passed", "failed", "not_exercised", "requires_approval"]:
        table.add_row(status, str(report.summary.get(status, 0)))
    console.print(table)
    for check in report.checks:
        console.print(f"- {check.id}: {check.status} ({check.component})")
    console.print(f"Detailed JSON: {artifact_path}")
    console.print(f"Next: {report.next_action}")


def _check_scan_artifact_current(workspace: Path) -> VerificationCheck:
    def run() -> VerificationCheck:
        scan_path = workspace / ".autoharness" / "scan.json"
        if not scan_path.exists():
            return VerificationCheck(
                id="scan_artifact_current",
                title="Scan artifact freshness",
                status=NOT_EXERCISED,
                component="scan",
                evidence=[".autoharness/scan.json was not present in the disposable workspace."],
                next_action="Run harness scan before verification when freshness must be proven.",
            )
        payload = json.loads(scan_path.read_text(encoding="utf-8"))
        current = scan_repository(workspace)
        current_hash = fingerprint_for_inventory(current.repository).inventory_hash
        artifact_hash = payload["fingerprint"]["inventory_hash"]
        status = PASSED if current_hash == artifact_hash else FAILED
        return VerificationCheck(
            id="scan_artifact_current",
            title="Scan artifact matches disposable workspace inventory",
            status=status,
            component="scan",
            evidence=[f"artifact={artifact_hash}", f"current={current_hash}"],
            next_action=(
                "Continue with plan/apply verification."
                if status == PASSED
                else "Rerun harness scan and harness plan before applying or verifying."
            ),
        )

    return _timed(run)


def _check_generated_python_importable(workspace: Path) -> VerificationCheck:
    def run() -> VerificationCheck:
        generated = workspace / ".autoharness" / "generated"
        if not generated.exists():
            return VerificationCheck(
                id="generated_python_importable",
                title="Generated Python files compile",
                status=NOT_EXERCISED,
                component="generation",
                evidence=["No generated AutoHarness Python files were present."],
                next_action="Run harness apply after approving a compatible generation plan.",
            )
        failures: list[str] = []
        compiled: list[str] = []
        for path in sorted(generated.rglob("*.py")):
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                failures.append(f"{path.relative_to(workspace)}: {exc.msg}")
            else:
                compiled.append(str(path.relative_to(workspace)))
        return VerificationCheck(
            id="generated_python_importable",
            title="Generated Python files compile",
            status=FAILED if failures else PASSED,
            component="generation",
            evidence=failures or compiled,
            next_action=(
                "Review generated syntax errors before running generated tests."
                if failures
                else "Generated Python syntax is deterministic and importable."
            ),
        )

    return _timed(run)


def _check_runtime_retry_and_redaction(workspace: Path) -> VerificationCheck:
    def run() -> VerificationCheck:
        clock = FakeClock()
        executor = RuntimeRetryExecutor(
            RetryPolicy(max_attempts=3, total_elapsed_budget_seconds=2),
            clock=clock,
        )
        log_path = workspace / ".autoharness" / "verify-runtime.jsonl"
        writer = RuntimeJsonlWriter(log_path)
        calls = 0

        def operation(attempt: int) -> str:
            nonlocal calls
            calls += 1
            if attempt == 1:
                raise RuntimeFailure(
                    RuntimeFailureKind.RATE_LIMITED,
                    "rate limited with sk-secret-token",
                    retry_after_seconds=0.1,
                )
            return "ok"

        outcome = executor.run(
            operation_id="verify-model-call",
            side_effect_classification=SideEffectClassification.READ_ONLY,
            operation=operation,
        )
        for entry in outcome.ledger.entries:
            writer.write_event(
                RuntimeEvent(
                    event_type=RuntimeEventType.RETRY_SCHEDULED,
                    run_id="verify",
                    operation_id=entry.operation_id,
                    attempt=entry.attempt,
                    timestamp_ms=entry.timestamp_ms,
                    status=entry.status,
                    failure_kind=entry.failure_kind,
                    fields={"raw_output": "sk-secret-token"},
                )
            )
        payload = log_path.read_text(encoding="utf-8")
        passed = (
            outcome.status is RuntimeStatus.SUCCESS and calls == 2 and "sk-secret" not in payload
        )
        return VerificationCheck(
            id="runtime_retry_redaction",
            title="Runtime retry is bounded and runtime logs are redacted",
            status=PASSED if passed else FAILED,
            component="runtime",
            evidence=[f"attempts={outcome.attempts}", f"sleeps={clock.sleeps}"],
            next_action=(
                "Runtime retry and redaction controls were exercised with fake provider failure."
                if passed
                else "Inspect runtime retry policy and redaction before trusting generated runners."
            ),
        )

    return _timed(run)


def _check_duplicate_side_effect_block(workspace: Path) -> VerificationCheck:
    def run() -> VerificationCheck:
        executor = RuntimeRetryExecutor(RetryPolicy(max_attempts=3), clock=FakeClock())
        commits = 0

        def operation(_: int) -> str:
            nonlocal commits
            commits += 1
            raise RuntimeFailure(
                RuntimeFailureKind.TIMEOUT_BEFORE_RESPONSE,
                "timeout after fake commit",
                side_effect_committed=True,
            )

        outcome = executor.run(
            operation_id="verify-side-effect",
            side_effect_classification=SideEffectClassification.UNKNOWN,
            operation=operation,
        )
        passed = outcome.status is RuntimeStatus.COMMIT_STATUS_UNKNOWN and commits == 1
        return VerificationCheck(
            id="duplicate_side_effect_block",
            title="Unknown committed side effect is not retried",
            status=PASSED if passed else FAILED,
            component="runtime",
            evidence=[f"status={outcome.status.value}", f"commits={commits}"],
            next_action=(
                "Duplicate side-effect prevention was exercised."
                if passed
                else "Fix retry policy before applying runtime harnesses to side-effecting tools."
            ),
        )

    return _timed(run)


def _check_sandbox_containment(
    workspace: Path,
    backend: DockerSandboxBackend,
) -> VerificationCheck:
    def run() -> VerificationCheck:
        probe = backend.probe()
        if probe.status is not SandboxCapabilityStatus.SUPPORTED:
            return VerificationCheck(
                id="sandbox_containment",
                title="Docker sandbox containment",
                status=FAILED,
                component="sandbox",
                evidence=[f"{cap.name}={cap.status.value}" for cap in probe.capabilities],
                next_action=(
                    "Build the sandbox image and ensure Docker can enforce requested policy."
                ),
            )
        source = workspace
        output = workspace.parent / "sandbox-output"
        code = (
            "import json, os, socket\n"
            "from pathlib import Path\n"
            "source_write_blocked=False\n"
            "try:\n"
            "    Path('/workspace/source/blocked.txt').write_text('bad')\n"
            "except OSError:\n"
            "    source_write_blocked=True\n"
            "Path('/workspace/output/result.txt').write_text('ok')\n"
            "network_denied=False\n"
            "try:\n"
            "    socket.create_connection(('1.1.1.1', 80), timeout=1)\n"
            "except OSError:\n"
            "    network_denied=True\n"
            "print(json.dumps({'uid': os.getuid(), "
            "'source_write_blocked': source_write_blocked, "
            "'network_denied': network_denied, "
            "'output_written': Path('/workspace/output/result.txt').read_text()}))\n"
        )
        result = backend.run(
            SandboxRequest(
                backend=SandboxBackendKind.DOCKER,
                source_root=source,
                output_dir=output,
                command=["python", "-B", "-c", code],
                resources=SandboxResources(cpus=0.5, memory_mb=128, pids_limit=32),
            )
        )
        evidence = json.loads(result.stdout.strip() or "{}")
        passed = (
            result.exit_code == 0
            and evidence.get("uid") == 65532
            and evidence.get("source_write_blocked") is True
            and evidence.get("network_denied") is True
            and evidence.get("output_written") == "ok"
        )
        return VerificationCheck(
            id="sandbox_containment",
            title="Sandbox blocks source writes and network while allowing approved output",
            status=PASSED if passed else FAILED,
            component="sandbox",
            evidence=[json.dumps(evidence, sort_keys=True)],
            next_action=(
                "Sandbox containment smoke passed for the supported Docker backend."
                if passed
                else "Treat sandbox verification as failed; do not claim containment."
            ),
        )

    return _timed(run)


def _check_original_tree_unchanged(root: Path, before_hash: str) -> VerificationCheck:
    def run() -> VerificationCheck:
        after_hash = _tree_hash(root)
        return VerificationCheck(
            id="original_tree_unchanged",
            title="Verification did not mutate the original working tree",
            status=(PASSED if before_hash == after_hash else FAILED),
            component="verification",
            evidence=[f"before={before_hash}", f"after={after_hash}"],
            next_action=(
                "Original tree remained unchanged."
                if before_hash == after_hash
                else "Inspect the working tree before continuing."
            ),
        )

    return _timed(run)


def _draft_evals(workspace: Path) -> list[EvalDraft]:
    drafts: list[EvalDraft] = []
    for path in sorted([workspace / "README.md", *workspace.glob("tests/test_*.py")]):
        if not path.exists() or not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                continue
            if "example" not in stripped.lower() and not stripped.startswith("def test_"):
                continue
            digest = hashlib.sha256(f"{path}:{line_no}:{stripped}".encode()).hexdigest()[:10]
            drafts.append(
                EvalDraft(
                    id=f"eval-draft-{digest}",
                    source_path=str(path.relative_to(workspace)),
                    source_line=line_no,
                    source_hash=_sha256_text(stripped),
                    candidate_task=stripped[:160],
                    approval_required=(
                        "Developer must approve expected concepts, allowed tool use, "
                        "and any grader."
                    ),
                )
            )
            if len(drafts) >= 10:
                return drafts
    return drafts


def _timed(callback: Callable[[], VerificationCheck]) -> VerificationCheck:
    started = time.monotonic()
    check = callback()
    return check.model_copy(update={"duration_ms": int((time.monotonic() - started) * 1000)})


def _summary(checks: list[VerificationCheck]) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "not_exercised": 0, "requires_approval": 0}
    for check in checks:
        counts[check.status] += 1
    return counts


def _next_action(checks: list[VerificationCheck]) -> str:
    if any(check.status == FAILED for check in checks):
        return "Resolve failed verification checks before claiming the harness is verified."
    if any(check.status == REQUIRES_APPROVAL for check in checks):
        return "Review draft semantic evals; deterministic controls that passed may be cited."
    if any(check.status == NOT_EXERCISED for check in checks):
        return "Add missing artifacts or supported fixtures to exercise skipped checks."
    return "All deterministic verification checks passed."


def _existing_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise AutoHarnessError(
            code="AH-V001",
            message="Verify target is not a directory.",
            context=ErrorContext(
                field="path",
                source="argument",
                expected="Existing repository directory.",
                next_action="Pass a repository directory to harness verify.",
            ),
            exit_code=5,
        )
    return resolved


def _copy_repository(source: Path, destination: Path) -> None:
    def ignore(_: str, names: list[str]) -> set[str]:
        ignored = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv"}
        return {name for name in names if name in ignored}

    shutil.copytree(source, destination, symlinks=True, ignore=ignore)


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    files = (item for item in root.rglob("*") if item.is_file() and ".git" not in item.parts)
    for path in sorted(files):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
