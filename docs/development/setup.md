# Development Setup

## Prerequisites

- Python 3.12
- [UV](https://docs.astral.sh/uv/)
- Docker Engine with Compose v2 for container and sandbox phases
- Git

Provider credentials are optional. The deterministic scanner and default tests must work without them.

## Local Environment

```bash
uv venv
uv pip install -r requirements-dev.txt
uv pip install --no-deps --no-build-isolation -e .
uv run harness --help
```

The canonical dependency declaration is `pyproject.toml`. `requirements.txt` and `requirements-dev.txt` exist for explicit UV pip workflows and container layer caching. Keep them synchronized until Phase 0 establishes automated export and lock checks.

After dependency resolution is available, create and commit `uv.lock`:

```bash
uv lock
uv sync --all-extras
```

## Environment Configuration

```bash
cp .env.example .env
```

Default:

```text
AUTOHARNESS_MODEL_PROVIDER=disabled
```

This is intentional. Only model-assisted tests need a configured provider.

Provider options:

- `groq` with `GROQ_API_KEY`
- `huggingface` with `HF_TOKEN`
- `openai_compatible` with base URL and API key

Never commit `.env` or tokens.

## Quality Commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Phase documents add targeted commands and acceptance checks.

## Docker Application Image

The root Dockerfile packages the AutoHarness CLI itself:

```bash
docker build -t autoharness:dev .
docker run --rm autoharness:dev --help
docker run --rm autoharness:dev --version
```

It follows the UV Docker pattern of copying the UV binary from its official image, installing requirements in a cacheable layer, and running as a non-root user.

## Compose Development Profile

```bash
docker compose build
docker compose run --rm autoharness --help
```

The repository is mounted read-only and the service drops Linux capabilities. Provider variables are forwarded only when they exist in the local environment.

This Compose service is for the AutoHarness application. It is not the untrusted target-code sandbox specified in Phase 6.

## Dependency Policy

- Add a dependency only when the standard library or an existing package does not provide a clear implementation.
- Keep provider SDKs behind adapters.
- Avoid heavyweight embedding or model-routing libraries until benchmarks justify them.
- Use lexical retrieval first; local embeddings are optional.
- Pin a reproducible lock before the first implementation release.
- Review transitive dependencies and container provenance before release.

## Test Layers

```text
tests/unit/          deterministic components
tests/contracts/     adapter and schema conformance
tests/integration/   CLI and component boundaries
tests/security/      negative and bypass cases
tests/fixtures/      small labeled repositories
tests/live/          opt-in provider smoke tests
```

Live tests use a marker and never run by default.

## Troubleshooting

### UV cannot build the local package

Confirm Python 3.12 is active and reinstall build tools from `requirements-dev.txt`, then run the editable install with `--no-build-isolation`.

### Docker cannot mount the repository

Check Docker Desktop file-sharing permissions. Do not weaken the read-only mount merely to make a scan pass.

### Provider test is rate limited

The default suite should not be using the live provider. Confirm the live-test marker and provider environment are opt-in.

### A dependency range resolves differently

Use the committed `uv.lock` after Phase 0. Requirements ranges describe compatibility, while the lock defines the tested environment.
