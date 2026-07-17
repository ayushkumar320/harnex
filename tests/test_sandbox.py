from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from autoharness.errors import AutoHarnessError
from autoharness.sandbox import (
    DockerSandboxBackend,
    SandboxCommandResult,
    SandboxRequest,
    SandboxResources,
)


@dataclass
class FakeCompleted:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class FakeRunner:
    def __init__(self, results: list[FakeCompleted | BaseException]) -> None:
        self.results = results
        self.calls: list[list[str]] = []

    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
    ) -> FakeCompleted:
        self.calls.append(list(args))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def test_docker_sandbox_builds_denied_by_default_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    output = tmp_path / "output"
    tmp = tmp_path / "tmp"
    source.mkdir()
    runner = FakeRunner(
        [
            FakeCompleted(returncode=0, stdout="25.0.0\n"),
            FakeCompleted(returncode=0, stdout="[]"),
            FakeCompleted(returncode=0, stdout="ok"),
        ]
    )

    result = DockerSandboxBackend(runner=runner).run(
        SandboxRequest(
            source_root=source,
            output_dir=output,
            tmp_dir=tmp,
            command=["python", "-c", "print('ok')"],
            env={"AUTOHARNESS_RUN_ID": "run-1"},
            resources=SandboxResources(cpus=0.5, memory_mb=128, pids_limit=32),
        )
    )

    assert result.status is SandboxCommandResult.COMPLETED
    command = runner.calls[2]
    assert command[:3] == ["docker", "run", "--rm"]
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--user") + 1] == "65532:65532"
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in command
    assert "--read-only" in command
    assert "--pids-limit" in command
    assert f"type=bind,src={source.resolve()},dst=/workspace/source,readonly" in command
    assert f"type=bind,src={output.resolve()},dst=/workspace/output" in command
    assert f"type=bind,src={tmp.resolve()},dst=/workspace/tmp" in command
    assert "AUTOHARNESS_RUN_ID=run-1" in command


def test_sandbox_fails_closed_when_docker_daemon_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner([FakeCompleted(returncode=1, stderr="cannot connect")])

    with pytest.raises(AutoHarnessError) as error:
        DockerSandboxBackend(runner=runner).run(
            SandboxRequest(
                source_root=source,
                output_dir=tmp_path / "output",
                command=["python", "-c", "print('nope')"],
            )
        )

    assert error.value.code == "AH-S001"
    assert error.value.exit_code == 5


def test_sandbox_fails_closed_when_sandbox_image_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner(
        [
            FakeCompleted(returncode=0, stdout="25.0.0\n"),
            FakeCompleted(returncode=1, stderr="No such image"),
        ]
    )

    with pytest.raises(AutoHarnessError) as error:
        DockerSandboxBackend(runner=runner).run(
            SandboxRequest(
                source_root=source,
                output_dir=tmp_path / "output",
                command=["python", "-c", "print('blocked')"],
            )
        )

    assert error.value.code == "AH-S001"


def test_sandbox_rejects_writable_paths_inside_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner(
        [
            FakeCompleted(returncode=0, stdout="25.0.0\n"),
            FakeCompleted(returncode=0, stdout="[]"),
        ]
    )

    with pytest.raises(AutoHarnessError) as error:
        DockerSandboxBackend(runner=runner).run(
            SandboxRequest(
                source_root=source,
                output_dir=source / "out",
                command=["python", "-c", "print('blocked')"],
            )
        )

    assert error.value.code == "AH-S003"


def test_sandbox_rejects_declared_symlink_writable_path_inside_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    outside = tmp_path / "outside"
    source.mkdir()
    outside.mkdir()
    link = source / "link-out"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unsupported: {exc}")
    runner = FakeRunner(
        [
            FakeCompleted(returncode=0, stdout="25.0.0\n"),
            FakeCompleted(returncode=0, stdout="[]"),
        ]
    )

    with pytest.raises(AutoHarnessError) as error:
        DockerSandboxBackend(runner=runner).run(
            SandboxRequest(
                source_root=source,
                output_dir=link / "out",
                command=["python", "-c", "print('blocked')"],
            )
        )

    assert error.value.code == "AH-S003"


def test_sandbox_rejects_traversal_back_into_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner(
        [
            FakeCompleted(returncode=0, stdout="25.0.0\n"),
            FakeCompleted(returncode=0, stdout="[]"),
        ]
    )

    with pytest.raises(AutoHarnessError) as error:
        DockerSandboxBackend(runner=runner).run(
            SandboxRequest(
                source_root=source,
                output_dir=source / ".." / "source" / "out",
                command=["python", "-c", "print('blocked')"],
            )
        )

    assert error.value.code == "AH-S003"


def test_sandbox_rejects_secret_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner(
        [
            FakeCompleted(returncode=0, stdout="25.0.0\n"),
            FakeCompleted(returncode=0, stdout="[]"),
        ]
    )

    with pytest.raises(AutoHarnessError) as error:
        DockerSandboxBackend(runner=runner).run(
            SandboxRequest(
                source_root=source,
                output_dir=tmp_path / "output",
                command=["python", "-c", "print('blocked')"],
                env={"GROQ_API_KEY": "sk-secret-token"},
            )
        )

    assert error.value.code == "AH-S009"
    assert "sk-secret-token" not in error.value.to_dict(verbose=True)["error"]["details"].values()


def test_sandbox_redacts_captured_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner(
        [
            FakeCompleted(returncode=0, stdout="25.0.0\n"),
            FakeCompleted(returncode=0, stdout="[]"),
            FakeCompleted(returncode=1, stderr="provider token sk-secret-token leaked"),
        ]
    )

    result = DockerSandboxBackend(runner=runner).run(
        SandboxRequest(
            source_root=source,
            output_dir=tmp_path / "output",
            command=["python", "-c", "raise SystemExit(1)"],
        )
    )

    assert result.status is SandboxCommandResult.FAILED
    assert result.stderr == "[redacted]"


def test_sandbox_timeout_returns_timeout_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("autoharness.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    source = tmp_path / "source"
    source.mkdir()
    runner = FakeRunner(
        [
            FakeCompleted(returncode=0, stdout="25.0.0\n"),
            FakeCompleted(returncode=0, stdout="[]"),
            subprocess.TimeoutExpired(cmd=["docker"], timeout=1, stderr=b"timed out"),
        ]
    )

    result = DockerSandboxBackend(runner=runner).run(
        SandboxRequest(
            source_root=source,
            output_dir=tmp_path / "output",
            command=["python", "-c", "while True: pass"],
            resources=SandboxResources(wall_time_seconds=1),
        )
    )

    assert result.status is SandboxCommandResult.TIMEOUT
    assert result.exit_code is None
