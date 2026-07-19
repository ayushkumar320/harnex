# Changelog

## Unreleased

- Made apply rollback restore existing generated targets and generated-base snapshots.
- Enforced provider attempt deadlines for synchronous SDK clients without blocking the async router.
- Moved external-evidence caching outside scanned repositories and revalidated cached provenance.
- Rejected repository symlinks before host-side verification reads.

## 0.0.0-alpha

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
- Docker sandbox support depends on the host Docker daemon and `autoharness-sandbox:dev` image.
- Semantic eval drafts require developer-approved oracles before scoring.
