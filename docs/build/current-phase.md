# Current Phase

We are building [Phase 4: Constrained generation](04-constrained-generation.md).

Current status: Phase 4 is complete. Phase 5 has not started.

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

Next phase:

- [Phase 5: Runtime reliability](05-runtime-reliability.md), after an explicit decision to begin
  runtime reliability work.

This pointer is intentionally simple. Update it when work moves to the next phase.
