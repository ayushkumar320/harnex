# Development Setup

## Prerequisites

- Python 3.12
- [UV](https://docs.astral.sh/uv/)
- Docker Engine with Compose v2 for container and sandbox phases
- Git

Provider credentials are optional for structural scanning and default tests. Full audit and planning are LLM-core and require a configured local or remote model outside mocked tests.

## Local Environment

```bash
uv sync --all-extras --locked
uv run harness --help
```

The canonical dependency declaration is `pyproject.toml`. `requirements.txt` and `requirements-dev.txt` exist for explicit UV pip workflows and container layer caching. Keep them synchronized until Phase 0 establishes automated export and lock checks.
The test suite checks that both requirements files match `pyproject.toml`.

## Environment Configuration

```bash
cp .env.example .env
```

Default (Phase 0):

```text
AUTOHARNESS_MODEL_PROVIDER=disabled
```

This is intentional. Only model-assisted tests need a configured provider.

Phase 2 replaces the single selector with an ordered `model_assistance.route` in the project
configuration. Environment variables provide secrets and model values for named route
entries; they do not silently create or reorder destinations. See
[Model-provider strategy](../architecture/model-providers.md).

Provider options:

- `groq` with `GROQ_API_KEY`
- `huggingface` with `HF_TOKEN`
- `openai_compatible` with base URL and API key
- Tavily external evidence with `TAVILY_API_KEY`; it is not a model provider

Never commit `.env` or tokens.

## Quality Commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Phase documents add targeted commands and acceptance checks.

## Local Scan Smoke

```bash
uv run harness scan tests/fixtures/repositories/basic_agent --output /tmp/autoharness-basic.json
uv run harness scan tests/fixtures/repositories/edge_cases --output /tmp/autoharness-edge.json
uv run harness scan tests/fixtures/repositories/unsupported_text --output /tmp/autoharness-unsupported.json
```

The scan command is read-only with respect to target code execution: it inventories files and parses
Python source as data. It writes only the requested report artifact.

## Provider Diagnostics

```bash
uv run harness doctor
uv run harness doctor --format json
```

`doctor` is repository-free. It reports configured model-assistance routes, missing credentials,
web-evidence settings, and the deterministic structural-inventory fallback without contacting
providers or sending repository evidence.

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
- Keep Tavily behind the separate `ExternalEvidenceProvider` boundary.
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

For an assisted command, inspect `harness doctor` and the attempt artifact. A rate-limited
route should be retried only when `Retry-After` fits the remaining deadline, then the next
eligible configured route should be used. Do not increase the global timeout as the first
remedy; confirm route order, cooldown state, and an independent fallback provider.

### A dependency range resolves differently

Use the committed `uv.lock` after Phase 0. Requirements ranges describe compatibility, while the lock defines the tested environment.
