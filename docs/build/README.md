# Build Plan

This directory turns the AgentHarness vision into independently executable delivery phases. Complete phases in order. A phase starts only after the previous phase's acceptance gates pass or a documented decision explicitly changes the dependency.

Every phase document contains a ready-to-use Codex prompt. The prompt is not a substitute for inspecting the repository: [`AGENTS.md`](../../AGENTS.md) remains the governing contract.

## Phase Map

| Phase | Outcome | Depends on |
| --- | --- | --- |
| [0. Foundation](00-foundation.md) | Reproducible UV project, CLI shell, schemas, quality gates, and containers | None |
| [1. Scanner and reports](01-scanner-and-report.md) | Read-only Python repository inventory, structural facts, and useful audit output | Phase 0 |
| [2. Providers and evidence](02-provider-and-retrieval.md) | Deadline-bounded multi-provider routing, local retrieval, and Tavily external evidence | Phase 1 |
| [3. Findings and planning UX](03-findings-and-planning.md) | Evidence-backed findings, support tiers, reviewable plan, and stable CLI contract | Phases 1-2 |
| [4. Constrained generation](04-constrained-generation.md) | Template generation, staged diffs, provenance, stale-plan checks, and safe reapply | Phase 3 |
| [5. Runtime reliability](05-runtime-reliability.md) | Structured logs, failure normalization, side-effect-aware retries, and attempt ledger | Phase 4 |
| [6. Sandbox enforcement](06-sandbox-enforcement.md) | Rootless Docker backend with capability verification and negative tests | Phases 4-5 |
| [7. Verification and evals](07-verification-and-evals.md) | Disposable verification, fault injection, deterministic evals, and draft semantic cases | Phase 6 |
| [8. Benchmark and alpha](08-benchmark-and-alpha.md) | Held-out benchmark, measured claims, package/container release, and alpha docs | Phases 0-7 |

## Milestones

### Milestone A: Useful without generation

Phases 0-3 produce a read-only auditor that works without provider credentials. This is the first product checkpoint.

### Milestone B: Safe supported transformation

Phases 4-6 produce generated controls for verified patterns and prove the enforcement backend's declared capabilities.

### Milestone C: Evidence for release

Phases 7-8 establish repeatable verification and replace design claims with benchmark measurements.

## Phase Operating Rules

- Read [`AGENTS.md`](../../AGENTS.md) before every phase.
- Re-read the active phase even when continuing an earlier task.
- Preserve previous public schema and CLI contracts unless the phase explicitly versions them.
- Do not use a live model in default tests.
- Do not claim completion from unit tests alone when the phase has a CLI or container outcome.
- Keep commits and changes scoped to one phase where practical.
- Record meaningful design changes in the relevant product or architecture document.
- Stop when acceptance gates pass; later-phase work remains later-phase work.

## Phase Completion Record

At the end of each phase, add a short implementation record to that phase document containing:

- Completion date and commit or revision
- Delivered behavior
- Acceptance commands and results
- Known limitations
- Decisions deferred to later phases

Do not mark a phase complete while required behavior is stubbed, skipped, or dependent on undocumented manual steps.

## Optional Next Plans

After the relevant baseline phases pass, see the
[final-year and product-extension roadmap](../nextplans/README.md). Those phases add
one-command orchestration, risk visualization, policy as code, controlled failure injection,
repair-effectiveness measurement, CI drift, and academic evaluation. They do not authorize
skipping or reordering this build plan.
