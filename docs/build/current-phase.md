# Current Phase

We are building [Phase 6: Sandbox enforcement](06-sandbox-enforcement.md).

Current status: Phase 5 is complete. Phase 6 has its first sandbox enforcement slice implemented:
typed sandbox contracts, a separate Docker target-execution image, fail-closed Docker/image probes,
doctor reporting, fake-backed negative tests, and a real Docker smoke for read-only source,
approved output writes, denied network, and non-root execution.

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

Current Phase 6 slices:

- Added `DockerSandboxBackend` with read-only source mount, approved writable output/tmp mounts,
  `--network none`, UID/GID `65532:65532`, dropped capabilities, `no-new-privileges`, CPU, memory,
  PID, and wall-time limits, redacted output capture, and environment allowlisting.
- Added `Dockerfile.sandbox` and `harness doctor` sandbox capability reporting.
- Added fake-backed negative tests for unavailable Docker, missing sandbox image, unsafe writable
  paths, secret environment variables, hostile output redaction, and timeout handling.
- Real Docker smoke passed on 2026-07-17: UID `65532`, source write blocked, network denied, and
  approved output write succeeded.

Remaining Phase 6 work before full completion:

- Expand real or fake conformance fixtures for CPU, memory, PID, symlink, traversal, and
  mount-boundary escape cases.
- Decide whether Phase 6 should expose a dedicated sandbox smoke command or leave execution solely
  to Phase 7 verification workflows.

This pointer is intentionally simple. Update it when work moves to the next phase.
