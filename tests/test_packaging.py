import json
import re
import tomllib
from importlib import metadata
from pathlib import Path

import agentharness

ROOT = Path(__file__).resolve().parents[1]


def _npm_package() -> dict[str, object]:
    return json.loads((ROOT / "npm" / "package.json").read_text(encoding="utf-8"))


def test_npm_wrapper_pins_the_python_version_it_ships_with() -> None:
    assert _npm_package()["pythonVersion"] == agentharness.__version__


def _distribution_name() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["name"])


def test_installed_distribution_version_matches_the_package() -> None:
    assert metadata.version(_distribution_name()) == agentharness.__version__


def test_npm_and_pypi_publish_under_the_same_name() -> None:
    assert _npm_package()["name"] == _distribution_name()


def test_pyproject_reads_its_version_from_the_package() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" in pyproject["project"]["dynamic"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/agentharness/__init__.py"


def test_distribution_declares_a_license_file() -> None:
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "npm" / "LICENSE").is_file()


def _semver_from_pep440(version: str) -> str:
    """Translate a PEP 440 version into the npm semver spelling of the same release."""
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?", version)
    if match is None:
        raise AssertionError(f"{version!r} is not a release or a/b/rc pre-release")
    release, kind, number = match.groups()
    if kind is None:
        return release
    return f"{release}-{ {'a': 'alpha', 'b': 'beta', 'rc': 'rc'}[kind] }.{number}"


def test_semver_translation_covers_releases_and_pre_releases() -> None:
    assert _semver_from_pep440("0.1.0") == "0.1.0"
    assert _semver_from_pep440("0.1.0a1") == "0.1.0-alpha.1"
    assert _semver_from_pep440("1.2.3b4") == "1.2.3-beta.4"
    assert _semver_from_pep440("1.0.0rc2") == "1.0.0-rc.2"


def test_npm_version_is_the_semver_spelling_of_the_python_version() -> None:
    package = _npm_package()
    assert package["version"] == _semver_from_pep440(str(package["pythonVersion"]))
