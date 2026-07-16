# Current Phase

We are building [Phase 3: Findings and planning UX](03-findings-and-planning.md).

Current status: Phase 3 is complete. Phase 4 has not started.

Completed slices:

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

Next phase:

- [Phase 4: Constrained generation](04-constrained-generation.md), after an explicit decision to
  begin generation work.

This pointer is intentionally simple. Update it when work moves to the next phase.
