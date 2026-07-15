import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _requirements(path: Path) -> list[str]:
    lines = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def test_runtime_requirements_match_project_dependencies() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert _requirements(ROOT / "requirements.txt") == pyproject["project"]["dependencies"]


def test_dev_requirements_match_project_optional_dependencies() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert _requirements(ROOT / "requirements-dev.txt") == [
        "-r requirements.txt",
        "hatchling>=1.27,<2",
        *pyproject["project"]["optional-dependencies"]["dev"],
    ]
