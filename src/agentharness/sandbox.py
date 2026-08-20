"""Capability-tested sandbox backend for constrained target execution."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field, field_validator

from agentharness.errors import AgentHarnessError, ErrorContext
from agentharness.runtime import redact_runtime_payload

SANDBOX_SCHEMA_VERSION = "1.0"
DEFAULT_SANDBOX_IMAGE = "agentharness-sandbox:dev"
CONTAINER_SOURCE = "/workspace/source"
CONTAINER_OUTPUT = "/workspace/output"
CONTAINER_TMP = "/workspace/tmp"
MAX_CAPTURE_CHARS = 16_384
ALLOWED_ENV_NAMES = frozenset({"AGENTHARNESS_RUN_ID", "PYTHONHASHSEED", "TZ"})
SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH")


class SandboxCapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"


class SandboxNetworkMode(StrEnum):
    DENY = "deny"


class SandboxBackendKind(StrEnum):
    DOCKER = "docker"


class SandboxCommandResult(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


class SandboxCapability(BaseModel):
    name: str
    status: SandboxCapabilityStatus
    evidence: str
    remediation: str | None = None


class SandboxCapabilityReport(BaseModel):
    schema_version: str = SANDBOX_SCHEMA_VERSION
    backend: SandboxBackendKind
    status: SandboxCapabilityStatus
    capabilities: list[SandboxCapability]
    containment_summary: list[str]

    def capability_map(self) -> dict[str, SandboxCapabilityStatus]:
        return {capability.name: capability.status for capability in self.capabilities}


class SandboxResources(BaseModel):
    cpus: float = Field(default=1.0, gt=0, le=4)
    memory_mb: int = Field(default=256, ge=64, le=4096)
    pids_limit: int = Field(default=64, ge=16, le=1024)
    wall_time_seconds: int = Field(default=10, ge=1, le=300)


class SandboxRequest(BaseModel):
    schema_version: str = SANDBOX_SCHEMA_VERSION
    backend: SandboxBackendKind = SandboxBackendKind.DOCKER
    image: str = DEFAULT_SANDBOX_IMAGE
    source_root: Path
    output_dir: Path
    tmp_dir: Path | None = None
    command: list[str]
    network: SandboxNetworkMode = SandboxNetworkMode.DENY
    env: dict[str, str] = Field(default_factory=dict)
    resources: SandboxResources = Field(default_factory=SandboxResources)

    @field_validator("command")
    @classmethod
    def command_must_be_explicit(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("sandbox command must not be empty")
        if any(not part for part in value):
            raise ValueError("sandbox command arguments must not be empty")
        return value


class SandboxResult(BaseModel):
    schema_version: str = SANDBOX_SCHEMA_VERSION
    backend: SandboxBackendKind
    status: SandboxCommandResult
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    capability_report: SandboxCapabilityReport
    containment_summary: list[str]


class CompletedProcessLike(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CompletedProcessLike:
        """Run a host command and return captured output."""


class SubprocessCommandRunner:
    """Subprocess-backed runner with text capture and no shell expansion."""

    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args),
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=dict(env) if env is not None else None,
        )


class DockerSandboxBackend:
    """Docker backend that fails closed unless required capabilities are supported."""

    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        docker_binary: str = "docker",
    ) -> None:
        self.runner = runner or SubprocessCommandRunner()
        self.docker_binary = docker_binary

    def probe(self, *, image: str = DEFAULT_SANDBOX_IMAGE) -> SandboxCapabilityReport:
        capabilities: list[SandboxCapability] = []
        docker_path = shutil.which(self.docker_binary)
        if docker_path is None:
            capabilities.append(
                SandboxCapability(
                    name="docker_daemon",
                    status=SandboxCapabilityStatus.UNSUPPORTED,
                    evidence="docker executable not found on PATH",
                    remediation="Install Docker Engine or Docker Desktop and retry doctor.",
                )
            )
            return _capability_report(capabilities)

        try:
            version = self.runner.run(
                [self.docker_binary, "version", "--format", "{{.Server.Version}}"],
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            capabilities.append(
                SandboxCapability(
                    name="docker_daemon",
                    status=SandboxCapabilityStatus.UNSUPPORTED,
                    evidence=f"docker daemon probe failed: {type(exc).__name__}",
                    remediation="Start Docker and confirm `docker version` succeeds.",
                )
            )
            return _capability_report(capabilities)

        if version.returncode != 0:
            capabilities.append(
                SandboxCapability(
                    name="docker_daemon",
                    status=SandboxCapabilityStatus.UNSUPPORTED,
                    evidence=_clean_capture(version.stderr or version.stdout),
                    remediation="Start Docker and confirm `docker version` succeeds.",
                )
            )
            return _capability_report(capabilities)

        capabilities.append(
            SandboxCapability(
                name="docker_daemon",
                status=SandboxCapabilityStatus.SUPPORTED,
                evidence=f"Docker server {version.stdout.strip() or 'available'}",
            )
        )
        image_probe = self.runner.run(
            [self.docker_binary, "image", "inspect", image],
            timeout=5,
        )
        if image_probe.returncode != 0:
            capabilities.append(
                SandboxCapability(
                    name="sandbox_image",
                    status=SandboxCapabilityStatus.UNSUPPORTED,
                    evidence=_clean_capture(image_probe.stderr or image_probe.stdout),
                    remediation=(
                        f"Build the target sandbox image with "
                        f"`docker build -f Dockerfile.sandbox -t {image} .`."
                    ),
                )
            )
            return _capability_report(capabilities)

        capabilities.append(
            SandboxCapability(
                name="sandbox_image",
                status=SandboxCapabilityStatus.SUPPORTED,
                evidence=f"{image} is available locally",
            )
        )
        capabilities.extend(
            [
                SandboxCapability(
                    name="read_only_source_mount",
                    status=SandboxCapabilityStatus.SUPPORTED,
                    evidence="backend uses a :ro bind mount for target source",
                ),
                SandboxCapability(
                    name="approved_writable_mounts",
                    status=SandboxCapabilityStatus.SUPPORTED,
                    evidence="backend mounts only output and tmp as writable",
                ),
                SandboxCapability(
                    name="network_denied",
                    status=SandboxCapabilityStatus.SUPPORTED,
                    evidence="backend passes --network none",
                ),
                SandboxCapability(
                    name="non_root_user",
                    status=SandboxCapabilityStatus.SUPPORTED,
                    evidence="backend passes --user 65532:65532",
                ),
                SandboxCapability(
                    name="linux_capabilities_dropped",
                    status=SandboxCapabilityStatus.SUPPORTED,
                    evidence="backend passes --cap-drop ALL and --security-opt no-new-privileges",
                ),
                SandboxCapability(
                    name="resource_limits",
                    status=SandboxCapabilityStatus.SUPPORTED,
                    evidence="backend passes memory, CPU, PID, and wall-time limits",
                ),
                SandboxCapability(
                    name="secret_environment_denied",
                    status=SandboxCapabilityStatus.SUPPORTED,
                    evidence="backend allowlists environment variable names",
                ),
            ]
        )
        return _capability_report(capabilities)

    def run(self, request: SandboxRequest) -> SandboxResult:
        report = self.probe(image=request.image)
        if report.status is not SandboxCapabilityStatus.SUPPORTED:
            raise _sandbox_blocked(
                "AH-S001",
                "Sandbox backend is not available.",
                "Start a supported Docker daemon and rerun doctor.",
            )
        _validate_request_paths(request)
        command = self._docker_command(request)
        started = time.monotonic()
        try:
            completed = self.runner.run(
                command,
                timeout=request.resources.wall_time_seconds + 2,
                env=_host_docker_env(),
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxResult(
                backend=SandboxBackendKind.DOCKER,
                status=SandboxCommandResult.TIMEOUT,
                exit_code=None,
                stdout=_clean_capture(exc.stdout or ""),
                stderr=_clean_capture(exc.stderr or "sandbox command exceeded wall-time limit"),
                duration_ms=_elapsed_ms(started),
                capability_report=report,
                containment_summary=report.containment_summary,
            )
        except OSError as exc:
            raise _sandbox_blocked(
                "AH-S002",
                "Sandbox command could not start.",
                "Confirm Docker is still available and retry.",
                details={"error_type": type(exc).__name__},
            ) from exc

        return SandboxResult(
            backend=SandboxBackendKind.DOCKER,
            status=(
                SandboxCommandResult.COMPLETED
                if completed.returncode == 0
                else SandboxCommandResult.FAILED
            ),
            exit_code=completed.returncode,
            stdout=_clean_capture(completed.stdout),
            stderr=_clean_capture(completed.stderr),
            duration_ms=_elapsed_ms(started),
            capability_report=report,
            containment_summary=report.containment_summary,
        )

    def _docker_command(self, request: SandboxRequest) -> list[str]:
        source = _normalized_existing_dir(request.source_root)
        output = _normalized_dir(request.output_dir)
        tmp_dir = _normalized_dir(request.tmp_dir) if request.tmp_dir else None
        safe_env = _validated_environment(request.env)
        output.mkdir(parents=True, exist_ok=True)
        if tmp_dir is not None:
            tmp_dir.mkdir(parents=True, exist_ok=True)

        command = [
            self.docker_binary,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65532:65532",
            "--cpus",
            _format_cpus(request.resources.cpus),
            "--memory",
            f"{request.resources.memory_mb}m",
            "--pids-limit",
            str(request.resources.pids_limit),
            "--workdir",
            CONTAINER_SOURCE,
            "--mount",
            f"type=bind,src={source},dst={CONTAINER_SOURCE},readonly",
            "--mount",
            f"type=bind,src={output},dst={CONTAINER_OUTPUT}",
        ]
        if tmp_dir is not None:
            command.extend(
                [
                    "--mount",
                    f"type=bind,src={tmp_dir},dst={CONTAINER_TMP}",
                ]
            )
        else:
            command.extend(["--tmpfs", f"{CONTAINER_TMP}:rw,noexec,nosuid,nodev,size=64m"])
        for name in sorted(safe_env):
            command.extend(["--env", f"{name}={safe_env[name]}"])
        command.append(request.image)
        command.extend(request.command)
        return command


def _capability_report(capabilities: list[SandboxCapability]) -> SandboxCapabilityReport:
    if any(cap.status is SandboxCapabilityStatus.UNSUPPORTED for cap in capabilities):
        status = SandboxCapabilityStatus.UNSUPPORTED
    elif any(cap.status is SandboxCapabilityStatus.UNVERIFIED for cap in capabilities):
        status = SandboxCapabilityStatus.UNVERIFIED
    else:
        status = SandboxCapabilityStatus.SUPPORTED
    return SandboxCapabilityReport(
        backend=SandboxBackendKind.DOCKER,
        status=status,
        capabilities=capabilities,
        containment_summary=[
            "source mounted read-only",
            "writes limited to approved output and tmp mounts",
            "network denied",
            "non-root container user",
            "Linux capabilities dropped with no-new-privileges",
            "CPU, memory, PID, and wall-time limits requested",
            "environment variables allowlisted",
        ],
    )


def _validate_request_paths(request: SandboxRequest) -> None:
    source = _normalized_existing_dir(request.source_root)
    output = _normalized_dir(request.output_dir)
    tmp_dir = _normalized_dir(request.tmp_dir) if request.tmp_dir else None
    if _is_same_or_within(output, source) or _declared_inside_source(request.output_dir, source):
        raise _sandbox_blocked(
            "AH-S003",
            "Sandbox output directory cannot be inside the read-only source tree.",
            "Choose an output directory outside the target repository snapshot.",
        )
    if tmp_dir is not None and (
        _is_same_or_within(tmp_dir, source) or _declared_inside_source(request.tmp_dir, source)
    ):
        raise _sandbox_blocked(
            "AH-S004",
            "Sandbox tmp directory cannot be inside the read-only source tree.",
            "Choose a tmp directory outside the target repository snapshot.",
        )
    if request.network is not SandboxNetworkMode.DENY:
        raise _sandbox_blocked(
            "AH-S005",
            "Sandbox network policy is unsupported.",
            "Use the default denied network policy.",
        )


def _normalized_existing_dir(path: Path) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise _sandbox_blocked(
            "AH-S006",
            "Sandbox source path could not be resolved.",
            "Use an existing directory as the sandbox source root.",
        ) from exc
    if not resolved.is_dir():
        raise _sandbox_blocked(
            "AH-S007",
            "Sandbox source path is not a directory.",
            "Use an existing directory as the sandbox source root.",
        )
    return resolved


def _normalized_dir(path: Path | None) -> Path:
    if path is None:
        raise ValueError("path is required")
    try:
        return path.expanduser().resolve(strict=False)
    except OSError as exc:
        raise _sandbox_blocked(
            "AH-S008",
            "Sandbox writable path could not be resolved.",
            "Use a normal filesystem directory without traversal or broken symlink components.",
        ) from exc


def _is_same_or_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _declared_inside_source(path: Path | None, source: Path) -> bool:
    if path is None:
        return False
    absolute = path.expanduser()
    if not absolute.is_absolute():
        absolute = Path.cwd() / absolute
    normalized_parts: list[str] = []
    for part in absolute.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    declared = Path(*normalized_parts)
    return declared == source or source in declared.parents


def _validated_environment(env: Mapping[str, str]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for name, value in env.items():
        secret_like_name = any(marker in name.upper() for marker in SECRET_ENV_MARKERS)
        if name not in ALLOWED_ENV_NAMES or secret_like_name:
            raise _sandbox_blocked(
                "AH-S009",
                "Sandbox environment contains a non-allowlisted or secret-like variable.",
                "Pass only documented sandbox environment names and never pass credentials.",
                details={"variable": name},
            )
        safe[name] = str(value)
    return safe


def _host_docker_env() -> dict[str, str]:
    safe_names = {"DOCKER_HOST", "DOCKER_CONTEXT", "HOME", "PATH"}
    return {name: value for name, value in os.environ.items() if name in safe_names}


def _clean_capture(value: object) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    redacted = redact_runtime_payload(text, MAX_CAPTURE_CHARS)
    if not isinstance(redacted, str):
        return "[redacted]"
    return redacted


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _format_cpus(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "1"


def _sandbox_blocked(
    code: str,
    message: str,
    next_action: str,
    *,
    details: dict[str, object] | None = None,
) -> AgentHarnessError:
    return AgentHarnessError(
        code=code,
        message=message,
        context=ErrorContext(
            field="sandbox",
            source="sandbox_backend",
            expected="capability-tested Docker backend with denied-by-default policy",
            next_action=next_action,
        ),
        exit_code=5,
        details=details,
    )


def default_sandbox_report() -> SandboxCapabilityReport:
    """Probe the default Docker sandbox backend for doctor output."""

    return DockerSandboxBackend().probe()


def temporary_sandbox_dirs(prefix: str = "agentharness-sandbox-") -> tuple[Path, Path]:
    """Create dedicated output and tmp directories for one constrained run."""

    root = Path(tempfile.mkdtemp(prefix=prefix))
    output = root / "output"
    tmp = root / "tmp"
    output.mkdir()
    tmp.mkdir()
    return output, tmp
