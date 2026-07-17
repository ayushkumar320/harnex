# Startup and Package Release Guide

This guide explains how to start AutoHarness locally, run the release gates, build distributable
artifacts, and publish the CLI as a Python package.

AutoHarness is packaged as a Python project in `pyproject.toml`. The installed command is:

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
uv run harness scan tests/fixtures/repositories/basic_agent --output /tmp/autoharness-basic.json
```

Run the alpha benchmark:

```bash
uv run harness benchmark --output docs/benchmark/alpha-results.json
```

## 2. Start With Docker

Build and run the application image:

```bash
docker build -t autoharness:dev .
docker run --rm autoharness:dev --help
docker run --rm autoharness:dev --version
```

Build the separate sandbox image:

```bash
docker build -f Dockerfile.sandbox -t autoharness-sandbox:dev .
```

Run sandbox-aware diagnostics:

```bash
uv run harness doctor --format json
uv run harness verify . --output .autoharness/verify.json
```

## 3. Release Readiness Checklist

Before publishing a package, confirm these are true:

- Choose a real package version. Do not publish `0.0.0`.
- Pick and add a license before public distribution.
- Confirm the package name `autoharness` is available on PyPI, or rename `[project].name`.
- Confirm `README.md`, `CHANGELOG.md`, `SECURITY.md`, and the support matrix are current.
- Confirm `docs/benchmark/alpha-results.json` reflects the latest benchmark run.
- Confirm no `.env`, token, credential, or local-only artifact is included.
- Confirm the Docker sandbox image builds and `harness verify` passes deterministic checks.

Recommended alpha version format:

```toml
version = "0.1.0a1"
```

Use a new version for every upload. PyPI does not allow replacing an already uploaded version.

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
docker build -t autoharness:dev .
docker run --rm autoharness:dev --help
docker build -f Dockerfile.sandbox -t autoharness-sandbox:dev .
uv run harness doctor --format json
uv run harness verify . --format json --output .autoharness/verify.json
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
autoharness-0.1.0a1.tar.gz
autoharness-0.1.0a1-py3-none-any.whl
```

## 6. Test The Built Wheel Locally

Create a clean virtual environment outside the repo:

```bash
python3.12 -m venv /tmp/autoharness-install-test
/tmp/autoharness-install-test/bin/python -m pip install --upgrade pip
/tmp/autoharness-install-test/bin/python -m pip install dist/*.whl
/tmp/autoharness-install-test/bin/harness --help
/tmp/autoharness-install-test/bin/harness doctor
```

Run a scan from the installed wheel:

```bash
/tmp/autoharness-install-test/bin/harness scan tests/fixtures/repositories/basic_agent \
  --output /tmp/autoharness-installed-scan.json
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
python3.12 -m venv /tmp/autoharness-testpypi
/tmp/autoharness-testpypi/bin/python -m pip install --upgrade pip
/tmp/autoharness-testpypi/bin/python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  autoharness==0.1.0a1
/tmp/autoharness-testpypi/bin/harness --help
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
python3.12 -m venv /tmp/autoharness-pypi
/tmp/autoharness-pypi/bin/python -m pip install --upgrade pip
/tmp/autoharness-pypi/bin/python -m pip install autoharness==0.1.0a1
/tmp/autoharness-pypi/bin/harness --help
```

## 9. Container Release

For an alpha container image, build with a matching tag:

```bash
docker build -t autoharness:0.1.0a1 .
docker run --rm autoharness:0.1.0a1 --help
```

If publishing to a registry, tag and push:

```bash
docker tag autoharness:0.1.0a1 ghcr.io/<owner>/autoharness:0.1.0a1
docker push ghcr.io/<owner>/autoharness:0.1.0a1
```

The sandbox image should be published separately if users need sandbox-backed verification:

```bash
docker build -f Dockerfile.sandbox -t ghcr.io/<owner>/autoharness-sandbox:0.1.0a1 .
docker push ghcr.io/<owner>/autoharness-sandbox:0.1.0a1
```

If you publish the sandbox image under a different name, update docs or configuration so users know
which image `harness verify` expects.

## 10. After Publishing

Update:

- `CHANGELOG.md` with the release date and artifact names.
- `README.md` installation section.
- `docs/benchmark/alpha-results.json` if any code changed after the last benchmark.
- Git tag, for example `v0.1.0a1`.

Suggested tag commands:

```bash
git tag -a v0.1.0a1 -m "AutoHarness 0.1.0a1"
git push origin v0.1.0a1
```

## Quick Start For Users After Publish

Once published, users should be able to run:

```bash
python3.12 -m pip install autoharness
harness --help
harness scan /path/to/agent-repo --output .autoharness/scan.json
harness plan .autoharness/scan.json --output .autoharness/plan.json
harness doctor
```

For verification:

```bash
docker build -f Dockerfile.sandbox -t autoharness-sandbox:dev .
harness verify /path/to/agent-repo --output .autoharness/verify.json
```

If you distribute a prebuilt sandbox image, replace the local build step with the documented image
pull or tag.
