# Next Phase N4: Repair Effectiveness Measurement

## Product Outcome

For supported repair families, AutoHarness compares original and approved repaired behavior
under identical controlled scenarios and reports whether reliability improved, regressed, or
remained inconclusive.

## User Problem

Generated code is not evidence of improvement. A repair may reduce one failure while adding
latency, attempts, dependencies, or behavioral regressions. Users need a comparable
before/after result before trusting the change.

## Prerequisites

- Build Phase 4 staged generation and safe apply
- Build Phases 5-7 runtime evidence and contained verification
- N3 deterministic Failure Injection Lab
- At least one verified repair adapter with a defined behavioral contract

## Scope

- Versioned `BehaviorSnapshot`, `BehaviorMetric`, `RepairComparison`, and
  `ImprovementVerdict` schemas.
- Paired execution of original and repaired snapshots using identical scenario, seed, fake
  adapters, inputs, resource policy, and observation contract.
- Initial metrics: terminal status, attempt count/order, elapsed virtual time, committed side
  effects, fallback result, redaction violations, log schema validity, and containment blocks.
- Secondary cost indicators: files, dependencies, configuration, and generated maintenance
  surface added by the repair.
- Verdicts: `improved`, `regressed`, `unchanged`, `inconclusive`, `not_exercised`.
- `harness improve` summary integration and standalone comparison artifact.

## Comparison Rules

- Correctness and safety invariants dominate availability and latency.
- A duplicate side effect cannot be offset by a faster response.
- Missing observations or unequal environments make the affected metric inconclusive.
- Semantic answer quality remains separate unless a developer-approved oracle exists.
- The model may explain validated differences but cannot choose the verdict.

## Deliverables

- Paired-run orchestrator over disposable original and repaired snapshots
- Metric registry and deterministic verdict rules
- Repair adapter contract declaring intended wins and permitted tradeoffs
- Human, JSON, and optional HTML comparison
- Fixtures for improvement, regression, unchanged, and inconclusive cases
- Rollback recommendation when a critical invariant regresses

## Acceptance Gates

- Original and repaired runs use identical hashed inputs, scenarios, seeds, fakes, and
  containment settings.
- A retry/idempotency repair proves exact commit count before it can be called improved.
- A provider-fallback repair reports availability gain plus attempts and latency budget.
- Critical safety regression blocks an overall improved verdict.
- Missing or mismatched evidence yields inconclusive, never inferred success.
- The original repository is never mutated by comparison.
- Results are reproducible under fake clocks and seeded inputs.

## Out of Scope

- Universal semantic correctness grading
- Claiming causal improvement from unrelated before/after environments
- Optimizing a single opaque score
- Automatically applying a repair because a comparison passed
- Comparing unsupported arbitrary rewrites

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Next Phase N4: repair effectiveness measurement.

Act as:
1. A senior experimental-systems engineer designing controlled paired comparisons and reproducible metrics.
2. A reliability engineer prioritizing safety invariants over superficial availability gains.
3. A product engineer communicating tradeoffs without collapsing them into an opaque score.

Before editing:
- Read AGENTS.md, security model, Build Phases 4-7, N3, this phase, and completion records.
- Inspect the actual generated manifest, verification report, runtime events, scenario results, and repair adapters.
- Select one repair family and define its intended behavioral contract before building a generic registry.

Implement comparison schemas:
- Define versioned BehaviorSnapshot, BehaviorMetric, MetricObservation, RepairComparison, Tradeoff, and ImprovementVerdict models.
- Record original/repaired snapshot hashes, plan and generated manifests, scenario and seed, adapters, containment, and observation completeness.
- Keep raw prompts and outputs excluded by default.

Implement paired runs:
- Create disposable original and repaired workspaces without mutating the target repository.
- Run identical failure scenarios with identical fakes, fake clocks, seed, inputs, environment allowlist, and resource limits.
- Compare terminal status, exact attempt order/count, virtual elapsed time, commit count, fallback path, redaction, log validity, containment, and cleanup.
- Record code/dependency/configuration surface added as a maintenance tradeoff, not a success metric.

Implement verdicts:
- Encode deterministic per-metric and overall rules.
- Let critical safety invariants dominate availability and performance.
- Emit improved, regressed, unchanged, inconclusive, or not_exercised with evidence.
- Permit model-generated explanation only after the verdict and cited observations are fixed.

Testing and UX:
- Golden-test a duplicate-side-effect repair, provider fallback repair, regression, no-op repair, missing observation, and environment mismatch.
- Show a concise before/after table, tradeoffs, confidence limitations, artifact path, and rollback recommendation.
- Integrate with improve only after explicit repair approval; comparison success never grants application permission.

Run all prerequisite and standard gates. Append the completion record with the repair families evaluated, metrics, observed tradeoffs, and validity limitations.
```

## Phase Completion Record

Not started.
