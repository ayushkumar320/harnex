# Current Phase

We are building [Phase 5: Runtime reliability](05-runtime-reliability.md).

Current status: Phase 4 is complete. Phase 5 implementation is complete; Docker acceptance
gates are pending because the local Docker daemon was unavailable.

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

Current Phase 5 slices:

- Added the initial runtime reliability core with versioned runtime events, redacted JSONL
  writing, normalized runtime failure kinds, side-effect classifications, an attempt ledger, and
  a deterministic retry executor.
- Added fault-injection tests for unsafe side-effect retry blocking, timeout after fake commit,
  bounded rate-limit retries, idempotency-key policy blocking, seeded jitter, logger write
  failure, hostile content, and default prompt/secret redaction.
- Added compact malformed-output correction packets before side effects, cancellation handling,
  human failure summaries, and generated direct-provider runtime adapters that run against fake
  providers.
- Generated runtime tests now exercise rate-limit retry behavior and malformed-output correction
  packets after applying the approved direct-provider plan.

Remaining Phase 5 gate:

- Run `docker build -t autoharness:dev .` and `docker run --rm autoharness:dev --help` after the
  Docker daemon is available, then append the final Phase 5 completion record.

This pointer is intentionally simple. Update it when work moves to the next phase.
