# Current Phase

We are building [Phase 3: Findings and planning UX](03-findings-and-planning.md).

Current status: Phase 3 is in progress, not complete.

Completed slices:

- Initial deterministic finding catalog with evidence-cited findings.
- Scan artifact and human summary include active finding counts, severity counts, and visible
  suppressions.
- `harness scan --fail-on` supports CI severity thresholds with exit code `1`.
- Read-only `harness plan` consumes completed scan artifacts and emits a versioned
  `HarnessPlan`.
- Scan artifacts include deterministic fingerprints and `harness plan` rejects stale repository
  snapshots or incompatible detector versions.

Remaining before Phase 3 completion:

- LLM candidate-finding synthesis path through the Phase 2 router.
- Deterministic acceptance validators for LLM-proposed findings and plan text.
- Documented CI examples.
- Final fixture precision measurement, docs, Docker gates, and completion record.

This pointer is intentionally simple. Update it when work moves to the next phase.
