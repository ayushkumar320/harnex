# CI Usage

Phase 3 supports read-only CI scanning with deterministic JSON artifacts and severity thresholds.
No model provider or network access is required for the default scan.

## Basic Gate

```bash
uv run harness scan . \
  --output .agentharness/scan.json \
  --fail-on high
```

This command exits:

| Code | Meaning |
| --- | --- |
| `0` | Scan completed and no active finding met the configured threshold |
| `1` | At least one active finding met `--fail-on` |
| `2` | Invalid command or configuration |
| `3` | Repository could not be analyzed, scan was empty, or scan was partial |
| `4` | Plan artifact is stale or requires unresolved approval |

Suppressed findings remain visible in `.agentharness/scan.json` but do not count toward
`--fail-on`.

## GitHub Actions Example

```yaml
name: agentharness

on:
  pull_request:
  push:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-extras --locked
      - run: uv run harness scan . --output .agentharness/scan.json --fail-on high
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: agentharness-scan
          path: .agentharness/scan.json
```

## GitLab CI Example

```yaml
agentharness_scan:
  image: python:3.12
  before_script:
    - pip install uv
    - uv sync --all-extras --locked
  script:
    - uv run harness scan . --output .agentharness/scan.json --fail-on high
  artifacts:
    when: always
    paths:
      - .agentharness/scan.json
```

## Read-Only Planning Check

To validate that a scan artifact can produce a reviewable plan without writing target files:

```bash
uv run harness scan . --output .agentharness/scan.json
uv run harness plan .agentharness/scan.json --output .agentharness/plan.json
```

`harness plan` rejects partial, stale, or incompatible scan artifacts with exit code `4`. A blocked
plan also exits `4` after writing the plan artifact, so CI systems should upload
`.agentharness/plan.json` on failure for review.

## Precision

There is no measured precision figure for AgentHarness on real repositories, and the fixture
corpus cannot supply one: the fixtures are hand-written to contain the patterns the detectors look
for, so agreement between them is a regression check, not evidence.

What is known from running the scanner across six real repositories on 2026-08-20:

- `AH-S201` produced no false positives after secret detection was changed to require a
  credential-shaped value rather than a credential name.
- `AH-R102` and `AH-S101` match every broad `except Exception` and every filesystem write or
  subprocess call. Those matches are accurate but high volume, and many flagged sites are
  deliberate. They are a review queue, not a defect count.

- `AH-R101` reports one finding per unguarded provider call. Detection is import-gated and
  covers OpenAI, Anthropic, Bedrock, Gemini, Groq, Mistral, Cohere, LiteLLM, Ollama, and
  Hugging Face call shapes. Providers reached through a wrapper library that renames the method
  chain are not detected.
- `AH-R103` matched 3 sites across 537 Python files in one real repository and no fixture
  negatives, so it is low volume by construction. It only fires on `while True` plus a handler
  with no exit.

Producing a defensible precision number requires hand-labeling the output on a corpus of real
agent repositories. Until that exists, do not publish a precision claim.
