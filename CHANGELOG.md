# Changelog

## Unreleased

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
