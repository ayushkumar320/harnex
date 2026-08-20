# Startup and Package Release Guide

This guide explains how to start AgentHarness locally, run the release gates, build distributable
artifacts, and publish the CLI as a Python package.

AgentHarness is packaged as a Python project in `pyproject.toml`. The installed command is:

```bash
harness
```

## 1. Start Locally

Prerequisites:

- Python 3.12
- UV
- Docker Engine or Docker Desktop, for sandbox-backed verification
- Git

Install dependencies:

```bash
uv sync --all-extras --locked
```

Check the CLI:

```bash
uv run harness --help
uv run harness --version
uv run harness doctor
```

Run a local scan:

```bash
uv run harness scan tests/fixtures/repositories/basic_agent --output /tmp/agentharness-basic.json
```

Run the alpha benchmark:

```bash
uv run harness benchmark --output docs/benchmark/alpha-results.json
```

## 2. Start With Docker

Build and run the application image:

```bash
docker build -t agentharness:dev .
docker run --rm agentharness:dev --help
docker run --rm agentharness:dev --version
```

Build the separate sandbox image:

```bash
docker build -f Dockerfile.sandbox -t agentharness-sandbox:dev .
```

Run sandbox-aware diagnostics:

```bash
uv run harness doctor --format json
uv run harness verify . --output .agentharness/verify.json
```

## 3. Release Readiness Checklist

Before publishing a package, confirm these are true:

- Confirm the version in `src/agentharness/__init__.py` is the one you intend to publish. It is the
  single source of truth: `pyproject.toml` reads it through `[tool.hatch.version]`, and
  `tests/test_packaging.py` fails if `npm/package.json` has drifted from it.
- Confirm `npm/package.json` carries both the PEP 440 version in `pythonVersion` and its semver
  spelling in `version`, for example `0.1.0a1` and `0.1.0-alpha.1`.
- Confirm `README.md`, `CHANGELOG.md`, `SECURITY.md`, and the support matrix are current.
- Confirm `docs/benchmark/alpha-results.json` reflects the latest benchmark run.
- Confirm no `.env`, token, credential, or local-only artifact is included.
- Confirm the Docker sandbox image builds and `harness verify` passes deterministic checks.

Bump the version in one place:

```python
# src/agentharness/__init__.py
__version__ = "0.1.0a1"
```

Then mirror it in `npm/package.json` as `pythonVersion` (`0.1.0a1`) and `version`
(`0.1.0-alpha.1`).

Use a new version for every upload. Neither PyPI nor npm allows replacing an already published
version.

## 4. Pre-Publish Gates

Run all quality gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Run product gates:

```bash
docker build -t agentharness:dev .
docker run --rm agentharness:dev --help
docker build -f Dockerfile.sandbox -t agentharness-sandbox:dev .
uv run harness doctor --format json
uv run harness verify . --format json --output .agentharness/verify.json
uv run harness benchmark --format json --output docs/benchmark/alpha-results.json
```

Expected current benchmark decision:

```text
alpha_decision: go
```

Only claim alpha support for the documented narrow support matrix.

## 5. Build The Python Package

Remove stale build output:

```bash
rm -rf dist
```

Build source distribution and wheel:

```bash
uv build
```

Inspect the output:

```bash
ls -l dist
```

You should see files like:

```text
agentharness-0.1.0a1.tar.gz
agentharness-0.1.0a1-py3-none-any.whl
```

## 6. Test The Built Wheel Locally

Create a clean virtual environment outside the repo:

```bash
python3.12 -m venv /tmp/agentharness-install-test
/tmp/agentharness-install-test/bin/python -m pip install --upgrade pip
/tmp/agentharness-install-test/bin/python -m pip install dist/*.whl
/tmp/agentharness-install-test/bin/harness --help
/tmp/agentharness-install-test/bin/harness doctor
```

Run a scan from the installed wheel:

```bash
/tmp/agentharness-install-test/bin/harness scan tests/fixtures/repositories/basic_agent \
  --output /tmp/agentharness-installed-scan.json
```

## 7. Publish To TestPyPI First

Create an API token on TestPyPI, then publish with UV:

```bash
export UV_PUBLISH_TOKEN="pypi-your-testpypi-token"
uv publish --publish-url https://test.pypi.org/legacy/ dist/*
```

Install from TestPyPI in a clean environment. Because dependencies usually come from real PyPI,
include PyPI as an extra index:

```bash
python3.12 -m venv /tmp/agentharness-testpypi
/tmp/agentharness-testpypi/bin/python -m pip install --upgrade pip
/tmp/agentharness-testpypi/bin/python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  agentharness==0.1.0a1
/tmp/agentharness-testpypi/bin/harness --help
```

If the package name is already taken, change `[project].name` before publishing.

## 8. Publish To PyPI

After TestPyPI works, create a PyPI API token and publish:

```bash
export UV_PUBLISH_TOKEN="pypi-your-production-token"
uv publish dist/*
```

Verify the public install:

```bash
python3.12 -m venv /tmp/agentharness-pypi
/tmp/agentharness-pypi/bin/python -m pip install --upgrade pip
/tmp/agentharness-pypi/bin/python -m pip install agentharness==0.1.0a1
/tmp/agentharness-pypi/bin/harness --help
```

## 9. Publish The npm Wrapper

Publish to PyPI first. The wrapper's `postinstall` step installs `agentharness==<pythonVersion>`
from PyPI into a private virtual environment, so a wrapper published ahead of the wheel would fail
on a fresh install.

Verify the wrapper against the published wheel, then publish it:

```bash
cd npm
node test-python.js
node install.js
node bin/harness.js --version
npm publish --provenance --access public
```

To test the wrapper before the matching version exists on PyPI, point it at a local wheel:

```bash
uv build
cd npm
AGENTHARNESS_PYTHON_REQUIREMENT="$(ls ../dist/*.whl)" node install.js
node bin/harness.js --version
```

## 10. Container Release

For an alpha container image, build with a matching tag:

```bash
docker build -t agentharness:0.1.0a1 .
docker run --rm agentharness:0.1.0a1 --help
```

If publishing to a registry, tag and push:

```bash
docker tag agentharness:0.1.0a1 ghcr.io/<owner>/agentharness:0.1.0a1
docker push ghcr.io/<owner>/agentharness:0.1.0a1
```

The sandbox image should be published separately if users need sandbox-backed verification:

```bash
docker build -f Dockerfile.sandbox -t ghcr.io/<owner>/agentharness-sandbox:0.1.0a1 .
docker push ghcr.io/<owner>/agentharness-sandbox:0.1.0a1
```

If you publish the sandbox image under a different name, update docs or configuration so users know
which image `harness verify` expects.

## 11. After Publishing

Update:

- `CHANGELOG.md` with the release date and artifact names.
- `README.md` installation section.
- `docs/benchmark/alpha-results.json` if any code changed after the last benchmark.
- Git tag, for example `v0.1.0a1`.

Suggested tag commands:

```bash
git tag -a v0.1.0a1 -m "AgentHarness 0.1.0a1"
git push origin v0.1.0a1
```

## Automated Release

`.github/workflows/release.yml` runs the whole sequence on a `v*` tag: it runs the quality gates,
checks the tag against `agentharness.__version__`, builds the distributions, publishes to PyPI,
waits for the release to be installable, smoke-tests and publishes the npm wrapper, and creates the
GitHub release.

It needs two things configured once:

- A PyPI trusted publisher for this repository and the `release.yml` workflow, so no PyPI token is
  stored in the repository.
- An `NPM_TOKEN` repository secret with publish rights, plus a `release` GitHub environment if you
  want manual approval before either upload.

The manual steps above remain the fallback when the workflow is unavailable.

## Quick Start For Users After Publish

Once published, users should be able to run:

```bash
pipx install agentharness
harness --help
harness scan /path/to/agent-repo --output .agentharness/scan.json
harness plan .agentharness/scan.json --output .agentharness/plan.json
harness doctor
```

For verification:

```bash
docker build -f Dockerfile.sandbox -t agentharness-sandbox:dev .
harness verify /path/to/agent-repo --output .agentharness/verify.json
```

If you distribute a prebuilt sandbox image, replace the local build step with the documented image
pull or tag.
