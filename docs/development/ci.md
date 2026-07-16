# CI Usage

Phase 3 supports read-only CI scanning with deterministic JSON artifacts and severity thresholds.
No model provider or network access is required for the default scan.

## Basic Gate

```bash
uv run harness scan . \
  --output .autoharness/scan.json \
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

Suppressed findings remain visible in `.autoharness/scan.json` but do not count toward
`--fail-on`.

## GitHub Actions Example

```yaml
name: autoharness

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
      - run: uv run harness scan . --output .autoharness/scan.json --fail-on high
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: autoharness-scan
          path: .autoharness/scan.json
```

## GitLab CI Example

```yaml
autoharness_scan:
  image: python:3.12
  before_script:
    - pip install uv
    - uv sync --all-extras --locked
  script:
    - uv run harness scan . --output .autoharness/scan.json --fail-on high
  artifacts:
    when: always
    paths:
      - .autoharness/scan.json
```

## Read-Only Planning Check

To validate that a scan artifact can produce a reviewable plan without writing target files:

```bash
uv run harness scan . --output .autoharness/scan.json
uv run harness plan .autoharness/scan.json --output .autoharness/plan.json
```

`harness plan` rejects partial, stale, or incompatible scan artifacts with exit code `4`. A blocked
plan also exits `4` after writing the plan artifact, so CI systems should upload
`.autoharness/plan.json` on failure for review.

## Fixture Precision Snapshot

The Phase 3 labeled fixtures were measured on 2026-07-16:

| Fixture | Labeled reportable findings | Reported findings | False positives |
| --- | ---: | ---: | ---: |
| `basic_agent` | 1 `AH-R101` | 1 | 0 |
| `edge_cases` | 2 `AH-S101`, 1 `AH-S201`, 1 `AH-U101` | 4 | 0 |
| `unsupported_text` | 0 | 0 | 0 |

Initial fixture precision: `5 / 5 = 1.00`. The unsupported fixture remains useful coverage for
status and inventory behavior, but it has no reportable Python findings.
