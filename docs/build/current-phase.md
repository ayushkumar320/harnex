# Current Phase

All baseline build phases through [Phase 8: Benchmark and alpha](08-benchmark-and-alpha.md) are complete.

Current status: Phase 8 completed on 2026-07-17 with a narrow public-alpha `go` decision backed by
the checked-in fixture benchmark. Future work should move to `docs/nextplans/` or explicitly open a
new post-alpha phase.

Previously completed Phase 3 slices:

- Initial deterministic finding catalog with evidence-cited findings.
- Scan artifact and human summary include active finding counts, severity counts, and visible
  suppressions.
- `harness scan --fail-on` supports CI severity thresholds with exit code `1`.
- Read-only `harness plan` consumes completed scan artifacts and emits a versioned
  `HarnessPlan`.
- Scan artifacts include deterministic fingerprints and `harness plan` rejects stale repository
  snapshots or incompatible detector versions.
- LLM-proposed finding candidates can flow through the Phase 2 router and are accepted only after
  deterministic schema, catalog, evidence ID, support-tier, generation-state, and local-path
  validation. This path is not wired into the default structural scan.
- LLM-proposed plan actions are accepted only after deterministic finding ID, adapter,
  permission, path, dependency, approval-state, and evidence validation.
- CI scan examples, fixture precision measurement, Docker gates, and the Phase 3 completion
  record are documented.

Completed Phase 4 slices:

- Initial `harness apply --dry-run` preview path for explicitly approved direct-provider
  generation plans.
- Approved generation plans stage deterministic template output only under `.autoharness/staging`
  and write a canonical `.autoharness/apply-preview.json` artifact.
- Phase 4 apply rejects non-dry-run invocation, unapproved actions, unsupported adapters, unsafe
  paths, stale scan artifacts, and missing generation actions before target writes.
- Declared output paths with existing symlink components are rejected before staging.
- `harness apply --yes` writes approved generated files with atomic replacement, records a
  transaction journal, and automatically rolls back files written earlier in the transaction when a
  later write fails.
- Existing generated target files are rejected without overwrite until three-way reapplication is
  implemented.
- Interactive confirmation is supported; declined approval exits cleanly without target writes.
- Three-way reapplication replaces unchanged generated bases, preserves append-only user edits,
  and rejects edits inside generated base regions with a conflict.
- Generated Python artifacts compile in a disposable fixture flow.
- AutoHarness-owned `.autoharness` artifact directory creation no longer makes scan freshness
  stale.

Completed Phase 6 slices:

- Added `DockerSandboxBackend` with read-only source mount, approved writable output/tmp mounts,
  `--network none`, UID/GID `65532:65532`, dropped capabilities, `no-new-privileges`, CPU, memory,
  PID, and wall-time limits, redacted output capture, and environment allowlisting.
- Added `Dockerfile.sandbox` and `harness doctor` sandbox capability reporting.
- Added fake-backed negative tests for unavailable Docker, missing sandbox image, unsafe writable
  paths, secret environment variables, hostile output redaction, and timeout handling.
- Real Docker smoke passed on 2026-07-17: UID `65532`, source write blocked, network denied, and
  approved output write succeeded.

Completed Phase 7 slices:

- Added `harness verify`, versioned verification reports, fake runtime fault checks, Docker
  sandbox smoke verification, draft semantic evals, and cleanup/non-mutation tests.

Completed Phase 8 slices:

- Added `harness benchmark`, a 10-case alpha corpus with 5 held-out cases, measured
  `docs/benchmark/alpha-results.json`, README/CHANGELOG/SECURITY/support-matrix updates, and a
  narrow alpha `go` decision.

This pointer is intentionally simple. Update it when work moves to the next phase.
