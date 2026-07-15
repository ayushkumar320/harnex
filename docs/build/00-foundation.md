# Phase 0: Foundation

## Product Outcome

A contributor can clone the repository, create an environment with UV, run a real `harness` CLI, execute quality checks, and build the application container from documented commands. No product command pretends to work before implementation.

## User Experience Outcome

The first interaction feels intentional and dependable. `harness --help` explains the product in plain language, `harness --version` is stable, invalid input is useful, and missing model credentials do not affect the CLI bootstrap.

## Scope

- Finalize Python package layout under `src/autoharness/`.
- Lock Python and dependency versions with UV.
- Establish Typer CLI root, global options, output-mode primitives, and error boundary.
- Define configuration precedence: flags -> environment -> config file -> defaults.
- Add base Pydantic schemas and schema-version convention.
- Configure Ruff, mypy, pytest, coverage, and test directories.
- Establish structured internal logging without exposing raw content.
- Verify the non-root Docker image and read-only Compose profile.
- Add CI for deterministic checks without provider credentials.

## Deliverables

- `uv.lock`
- Package metadata and `harness` console script
- `autoharness.cli`, configuration, error, and schema modules
- Unit tests for config and CLI behavior
- Container smoke test
- Dependency synchronization check between `pyproject.toml` and requirements files
- Updated development documentation

## Acceptance Gates

```bash
uv sync --all-extras --locked
uv run harness --help
uv run harness --version
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
docker build -t autoharness:phase-0 .
docker run --rm autoharness:phase-0 --version
```

The CLI must work with all provider variables unset. Help and error output must remain readable with `NO_COLOR=1`.

## Out of Scope

- Repository scanning
- Model-provider calls
- Harness generation
- Target-code execution
- Sandbox backend implementation

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Phase 0.

Adopt three responsibilities at once:
1. Act as a senior Python platform engineer: create a minimal, typed, testable foundation with stable public boundaries and no speculative framework.
2. Think as a product manager: protect the audit-first product direction, keep scope to foundation work, and make every dependency justify a near-term user outcome.
3. Act as the user's UX steward: the user should feel oriented, safe, and confident from the first command. Help and errors must be calm, concise, and actionable.

Before editing:
- Read AGENTS.md completely and follow it as the governing contract.
- Read README.md, docs/product/vision.md, docs/product/user-experience.md, docs/architecture/overview.md, docs/architecture/security.md, and docs/development/setup.md.
- Inspect all current files and preserve user changes.
- Report the exact Phase 0 scope and any conflict you find between documentation and the repository.

Implement:
- A Python 3.12 src-layout package with a stable `harness` entry point.
- Root CLI global options for version, output format, verbosity, color behavior, and config path, without adding fake scan/plan behavior.
- Typed configuration with documented precedence and no provider credential requirement.
- A small internal error taxonomy with stable error codes and one terminal rendering boundary.
- Versioned base artifact models that later schemas can inherit from.
- Ruff, strict mypy, pytest, coverage, and CI configuration.
- UV locking and a reproducible dependency workflow. Keep requirements exports synchronized or automate the check.
- A non-root application image and read-only Compose smoke path. Do not call this image the target sandbox.

Engineering constraints:
- Do not call a model or network service.
- Do not execute target repository code.
- Keep provider SDKs out of core types.
- Do not add abstractions for scanners or generators beyond the smallest typed protocol needed by the foundation.
- Make output deterministic and tests independent of terminal color.
- Use structured internal events and redact before rendering.

UX requirements:
- `harness --help` must communicate audit first, generate second.
- Invalid configuration must name the field, source, expected value, and next action without a traceback by default.
- `--verbose` may add diagnostic context but must never expose secrets.
- Respect NO_COLOR and non-interactive output.

Testing requirements:
- Test configuration precedence, invalid values, missing optional credentials, output modes, version output, error rendering, and NO_COLOR.
- Build and run the Docker image.
- Run all acceptance commands in this document and fix failures.

Do not mark the phase complete until the acceptance gates pass. Finish by updating relevant docs and append a Phase Completion Record with delivered behavior, commands run, results, limitations, and deferred work.
```

## Phase Completion Record

### 2026-07-15

- Delivered a typed Phase 0 CLI foundation with global options for version, output format,
  config path, color mode, verbosity, and quiet output. Product commands remain intentionally
  absent until their build phases.
- Added configuration loading with precedence `flags -> environment -> config file -> defaults`,
  user-facing configuration errors, base schema models, and redacted structured logging setup.
- Added tests for CLI bootstrap behavior, configuration precedence and invalid values,
  `NO_COLOR`, JSON error rendering, logging redaction, and dependency synchronization.
- Added coverage configuration and a CI workflow for UV, Ruff, mypy, pytest, and application
  container smoke checks.
- Acceptance commands run successfully: `uv sync --all-extras --locked`,
  `uv run harness --help`, `uv run harness --version`, `NO_COLOR=1 uv run harness --format xml`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest`.
- Container acceptance commands now pass: `docker build -t autoharness:phase-0 .` and
  `docker run --rm autoharness:phase-0 --version`.
- Deferred to later phases: repository scanning, provider routing, external evidence retrieval,
  generation, target-code execution, and sandbox enforcement.
