# Changelog

## 0.1.0a2

- Renamed the PyPI and npm distribution from `agentharness` to `agentgap`. PyPI rejects
  `agentharness` as too similar to the existing `agent-harness` project, which strips separators
  when comparing names. The import package stays `agentharness`, as does the `.agentharness/`
  artifact directory, the `AGENTHARNESS_` environment prefix, the sandbox image name, and the
  `harness` command; `agent-harness` installs a module named `agent_harness`, so there is no import
  collision to resolve.
- Excluded vendored dependencies from the scan. `DEFAULT_EXCLUDED_DIRS` covered `.venv` and
  `node_modules` but not `vendor`, `venv`, `env`, `site-packages`, `third_party`,
  `bower_components`, or `.eggs`, so third-party code was audited as if it were first-party. On one
  measured repository 15,725 of 16,505 findings came from `vendor/`.
- Fixed `AH-S201` false positives on documentation. Secret detection matched credential names
  rather than credential values, so any README or `.env.example` documenting
  `GROQ_API_KEY=your_groq_api_key` was flagged and silently excluded from analysis.
  `_looks_secret_content` now requires a credential name followed by a credential-shaped value on
  the same line and rejects placeholder values. Restricting the value to its own line matters:
  `\s` would let `KEY=\nNEXT_VAR` capture the following variable name. The PEM check is now one
  contiguous pattern, so a secret scanner carrying `-----BEGIN ` and `PRIVATE KEY-----` as separate
  constants no longer flags its own source. Measured across six repositories, total findings fell
  from 16,798 to 1,016 and `AH-S201` false positives to zero.
- Added `harness report`, which renders a scan artifact as a Markdown brief grouped by severity
  with file, line, and symbol evidence per finding. Generation covers only `AH-R101`, so on most
  repositories the findings are the whole deliverable.
- Bare `harness` now runs a read-only audit of the current directory instead of printing help.
- Corrected the project URLs in `pyproject.toml` and `npm/package.json`, which pointed at a
  repository that does not exist.
- Rewrote the README and the npm README around the failure modes the tool detects, a walkthrough
  with real output, and an explicit statement of what the tool does not do.
- Removed `docs/build/`, the phase-by-phase implementation plans, now that the baseline is built.
- Added `harness audit`, `harness improve`, and `harness check`: one-command workflows that compose
  the existing scan, plan, approve, apply, and verify primitives and record a versioned
  `workflow_run` artifact at `.agentharness/workflow.json`. `audit` stays read-only, and `improve`
  requires separate approvals for the plan and for the exact staged files.
- Added `harness approve`, which records explicit human approval on a plan artifact. Without it the
  deterministic planner could only emit `unresolved` actions, so `harness apply` was unreachable
  from a real `harness plan` run.
- The planner now proposes the direct-provider generation templates as a
  `write_generated_files` action instead of a `review_only` placeholder, connecting planning to the
  existing generation templates.
- Verification now reports an unavailable Docker sandbox as `not_exercised` instead of `failed`, so
  `harness verify` no longer fails on machines without Docker while still reporting incompleteness.

## 0.1.0a1

- Renamed the distribution and import package from `autoharness` to `agentharness`. The PyPI name
  `autoharness` belongs to an unrelated project, so the old import name could collide in a shared
  environment. Artifact directories are now `.agentharness/`, environment variables use the
  `AGENTHARNESS_` prefix, and the sandbox image is `agentharness-sandbox`. The CLI command is
  still `harness`.
- Added the MIT license.
- Added an npm wrapper package that installs the matching Python wheel into a private virtual
  environment and forwards arguments and exit codes to the `harness` CLI.
- Added packaging metadata: authors, license, keywords, classifiers, and project URLs. The version
  is now read from `agentharness.__version__` so it has a single source of truth.
- Made apply rollback restore existing generated targets and generated-base snapshots.
- Enforced provider attempt deadlines for synchronous SDK clients without blocking the async router.
- Moved external-evidence caching outside scanned repositories and revalidated cached provenance.
- Rejected repository symlinks before host-side verification reads.

## 0.0.0-alpha (unpublished)

- Added read-only Python repository scanning with versioned JSON reports.
- Added evidence-backed deterministic findings and read-only planning.
- Added constrained direct-provider generation with staged previews, apply transactions, rollback,
  and three-way reapply checks.
- Added runtime reliability primitives for JSONL events, redaction, retry policy, attempt ledgers,
  malformed-output correction packets, and human failure summaries.
- Added a Docker sandbox backend with a separate target-execution image and doctor capability
  reporting.
- Added `harness verify` for deterministic verification checks in a disposable workspace.
- Added `harness benchmark` and a 10-case labeled alpha corpus with held-out fixtures.

Known alpha limits:

- Python only; TypeScript and framework adapters are not alpha-supported.
- Direct-provider generation is limited to the verified fixture pattern.
- Default tests and benchmark do not make live provider calls.
- Docker sandbox support depends on the host Docker daemon and `agentharness-sandbox:dev` image.
- Semantic eval drafts require developer-approved oracles before scoring.
