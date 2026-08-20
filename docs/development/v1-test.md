# V1 Test Guide

This guide is the plain-English path for testing the current AgentHarness v1/public-alpha
candidate from a fresh checkout.

Use it when you want to answer three simple questions:

- Does the CLI start?
- Do the main commands work without provider credentials?
- What is still release or roadmap work rather than shipped behavior?

## 1. Prepare the machine

Install these first:

- Python 3.12
- UV
- Docker Engine or Docker Desktop
- Git

Then install the project dependencies from the repository root:

```bash
uv sync --all-extras --locked
```

In layman language: this creates the local Python environment exactly from the locked dependency
file, so everyone tests the same package versions.

## 2. Check that the CLI opens

```bash
uv run harness --help
uv run harness --version
uv run harness doctor
```

Expected result:

- `--help` shows the available commands.
- `--version` prints the current package version.
- `doctor` says it does not send repository evidence and reports provider, web-evidence, and
  sandbox readiness.

No API keys are needed for this.

## 3. Run the read-only scans

```bash
uv run harness scan tests/fixtures/repositories/basic_agent --output /tmp/agentharness-basic.json
uv run harness scan tests/fixtures/repositories/edge_cases --output /tmp/agentharness-edge.json
uv run harness scan tests/fixtures/repositories/unsupported_text --output /tmp/agentharness-unsupported.json
```

Expected result:

- The command reads files as data.
- It does not import the target repository.
- It does not run target tests, setup scripts, tools, or model calls.
- It writes the JSON report to the path you gave with `--output`.

In layman language: this is the safe first look. AgentHarness should be able to tell you what it
found and what it could not understand without touching the target app.

## 4. Scan this repository and create a plan

```bash
uv run harness scan . --output .agentharness/scan.json
uv run harness plan .agentharness/scan.json --output .agentharness/plan.json
```

Expected result:

- `scan` writes `.agentharness/scan.json`.
- `plan` reads that scan artifact and writes `.agentharness/plan.json`.
- If the plan is blocked, the command exits with code `4` after writing the artifact for review.

In layman language: scan finds the issues; plan explains what AgentHarness could safely propose
next. A blocked plan is not necessarily a crash. It can mean AgentHarness found something it should
not generate for automatically.

## 5. Preview generation before applying anything

Only run this after a plan exists. A fresh plan always arrives unapproved, so record approval
first:

```bash
uv run harness approve .agentharness/plan.json --yes
uv run harness apply .agentharness/plan.json --dry-run --output .agentharness/apply-preview.json
```

Expected result of `approve`:

- Actions matching a supported generation template become `approved` in the plan artifact.
- Any other action is left untouched and listed as unapproved.
- If nothing can be approved, the command exits with code `4` and the plan is not modified.

Expected result:

- Approved generated files are staged under `.agentharness/staging/`.
- A preview manifest is written to `.agentharness/apply-preview.json`.
- Target source files are not changed during `--dry-run`.

In layman language: this is the "show me what you would write" step.

To actually apply approved generated files, run:

```bash
uv run harness apply .agentharness/plan.json --yes --output .agentharness/apply-preview.json
```

Expected result:

- AgentHarness writes only approved generated files.
- It records a transaction journal under `.agentharness/transactions/`.
- If a later write fails, earlier writes in that transaction are rolled back.

Do not run the apply command on a user repository unless the preview is acceptable.

## 5b. The same flow in one command

```bash
uv run harness audit tests/fixtures/repositories/basic_agent
uv run harness improve tests/fixtures/repositories/basic_agent
uv run harness check tests/fixtures/repositories/basic_agent --fail-on high
```

Expected result:

- `audit` runs scan and plan, writes `.agentharness/workflow.json` inside the target repository,
  and changes no target source file.
- `improve` prompts twice: once to approve the plan, once to apply the exact staged files.
  Answering `n` to either exits with code `4` and writes no generated file.
- `check` exits `1` when active findings reach the `--fail-on` severity, and `0` otherwise.

In layman language: `audit` is the safe look, `improve` is the guided repair, and `check` is the
CI gate. They call the same code as the low-level commands above.

## 6. Build the sandbox image

```bash
docker build -f Dockerfile.sandbox -t agentharness-sandbox:dev .
```

Expected result:

- Docker builds the target-execution sandbox image.
- This image is separate from the AgentHarness application image.

In layman language: the sandbox image is the locked-down place used for verification checks. The
regular app image is just the CLI package.

## 7. Run verification

```bash
uv run harness verify . --output .agentharness/verify.json
uv run harness verify . --format json --output .agentharness/verify.json
```

Expected result:

- Verification writes `.agentharness/verify.json`.
- It uses disposable workspace checks, fake runtime failures, denied-network sandbox checks, and
  draft semantic eval status.
- If any verification check fails, the command exits with code `5`.

In layman language: this does not prove production safety. It proves the specific checks named in
the verification report.

## 8. Run the alpha benchmark

```bash
uv run harness benchmark --output docs/benchmark/alpha-results.json
uv run harness benchmark --format json --output docs/benchmark/alpha-results.json
```

Expected result:

- The benchmark runs the checked-in alpha fixture corpus.
- It does not call live model providers.
- The current expected decision is `go` for the narrow documented alpha support matrix.

In layman language: this is the repeatable scorecard for the current fixture set. It is evidence
for the alpha claim, not proof that all real-world agent repositories are covered.

## 9. Run the full local quality gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Expected result:

- Lint passes.
- Formatting check passes.
- Type checking passes.
- The default test suite passes without live provider calls.

## 10. Build and test the application image

```bash
docker build -t agentharness:dev .
docker run --rm agentharness:dev --help
docker run --rm agentharness:dev --version
```

Expected result:

- The application image builds.
- The installed CLI starts inside the container.
- The container runs as the packaged AgentHarness app, not as the target-code sandbox.

## 11. Optional package build check

Run this before publishing, not for every small code change:

```bash
uv build
ls -l dist
```

Expected result:

- A source distribution and wheel appear in `dist/`.

To test the wheel locally:

```bash
python3.12 -m venv /tmp/agentharness-install-test
/tmp/agentharness-install-test/bin/python -m pip install --upgrade pip
/tmp/agentharness-install-test/bin/python -m pip install dist/*.whl
/tmp/agentharness-install-test/bin/harness --help
/tmp/agentharness-install-test/bin/harness doctor
/tmp/agentharness-install-test/bin/harness scan tests/fixtures/repositories/basic_agent --output /tmp/agentharness-installed-scan.json
```

Expected result:

- The built package installs in a clean environment.
- The installed `harness` command works outside the development virtual environment.

## Exit codes to know

| Code | Meaning |
| --- | --- |
| `0` | Command completed and passed its configured gate |
| `1` | CI threshold or benchmark decision failed |
| `2` | Invalid command or configuration |
| `3` | Repository scan failed, was empty, or was partial |
| `4` | Plan/apply approval or freshness problem |
| `5` | Verification or sandbox capability failed |

## What is left after this v1 test

Development/release chores still left before external distribution:

- Confirm the version in `src/agentharness/__init__.py` is the one you intend to publish.
- Add a license before public distribution or external contributions.
- Confirm the PyPI package name or rename the project before publishing.
- Generate and review SBOM/provenance artifacts for release.
- Publish to TestPyPI/PyPI only after the clean wheel test passes.
- Publish container images only after deciding registry names and tags.

Optional product work still left in `docs/nextplans/`:

- N0: one-command `audit`, `improve`, and `check` workflows.
- N1: execution-risk graph and self-contained HTML report.
- N2: reliability policy as code.
- N3: deterministic failure injection lab.
- N4: before/after repair-effectiveness measurement.
- N5: CI drift and pull-request baseline checking.
- N6: final-year benchmark, evaluation report, and demonstration.
