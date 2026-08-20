# Next Plans: Final-Year Product Extensions

This directory contains optional extensions that can turn the AgentHarness baseline into a
measurable final-year project. These plans do not replace or reorder
[`docs/build/`](../build/README.md). A next-plan phase begins only after its listed baseline
prerequisites have passed and their completion records are current.

The academic and product thesis is:

> AgentHarness should not merely recommend reliability improvements. It should show the
> evidence for a risk and measure whether an approved repair changes behavior under a
> controlled failure.

## Recommended Phase Map

Current implementation status as of 2026-08-20: the baseline build phases through Phase 8 are
complete, N0 is partially delivered (see its completion record for the deferred parts), and every
other next-plan phase below is still not started. Treat this table as the remaining
product-extension backlog, not shipped functionality.

| Phase | Outcome | Baseline prerequisite |
| --- | --- | --- |
| [N0. One-command workflows](00-one-command-workflows.md) | `audit`, `improve`, and `check` orchestrate existing primitives safely | Build Phase 3 for `audit`; Phases 4 and 7 for full `improve` |
| [N1. Execution-risk graph](01-execution-risk-graph.md) | Evidence-linked graph plus accessible HTML audit report | Build Phase 3 |
| [N2. Policy as code](02-policy-as-code.md) | Versioned organization policy with explainable evaluation | Build Phase 3 |
| [N3. Failure Injection Lab](03-failure-injection-lab.md) | Deterministic failure scenarios exercised in containment | Build Phases 5-7 |
| [N4. Repair effectiveness](04-repair-effectiveness.md) | Before/after behavioral comparison for approved repairs | N3 and Build Phases 4-7 |
| [N5. CI drift checking](05-ci-drift-checking.md) | Baseline-to-current PR reliability checks | N2 and Build Phase 3 |
| [N6. Benchmark and final-year evaluation](06-benchmark-and-final-evaluation.md) | Reproducible corpus, metrics, report, and demonstration | Selected N0-N5 phases |

## Minimum Viable Final-Year Track

If time is constrained, implement:

1. Build Phases 0-3: trustworthy read-only audit.
2. N0 read-only `harness audit .` orchestration.
3. N1 execution-risk graph and HTML report.
4. A constrained subset of N3 with fake providers and one fake side effect.
5. N4 comparison for one repair family.
6. N6 benchmark and written evaluation.

This track proves the central idea without requiring arbitrary code generation, every agent
framework, or a production hosted service.

## Full Product Track

After Build Phases 4-7 pass, add policy, repair measurement, and CI drift. The complete user
journey becomes:

```text
harness audit .
    -> read-only facts, findings, risk graph, and optional policy result

harness improve .
    -> reuse current audit, propose a plan, stage a diff, request approval,
       apply approved changes, inject controlled failures, and compare behavior

harness check .
    -> compare the current snapshot with an approved baseline for CI
```

The low-level `scan`, `plan`, `apply`, `verify`, and `doctor` commands remain public for
automation and diagnosis. Orchestration must preserve every permission and containment
boundary of the underlying commands.

## Remaining Work Summary

- N0 is partially delivered: `audit`, `improve`, and `check` ship, while artifact cache reuse,
  resumption flags, and the optional model stage remain.
- N1 remains to make findings easier to understand through an evidence-linked risk graph and HTML
  report.
- N2 remains to let teams express versioned reliability policy instead of relying only on severity
  thresholds.
- N3 remains to exercise controlled failures under the verified containment boundary.
- N4 remains to prove whether approved repairs improve behavior in before/after scenarios.
- N5 remains to compare pull requests against an approved baseline and catch drift without blocking
  on historical debt.
- N6 remains to turn the selected next-plan work into a reproducible final-year evaluation.

## Research Questions

The evaluation should answer:

1. How precisely can static analysis detect agent-specific reliability risks?
2. Does bounded LLM interpretation improve useful findings without increasing unacceptable
   false positives?
3. Can controlled repairs reduce seeded failures while preserving normal behavior?
4. Can side-effect-aware retry handling prevent duplicate committed operations?
5. How much availability does multi-provider fallback add, and at what latency and attempt
   cost?
6. Which dynamic repository patterns remain unsupported?
7. Does the risk graph reduce the time required to understand a finding?

## Shared Rules

- Read [`AGENTS.md`](../../AGENTS.md) and all prerequisite completion records before work.
- Do not mark a next-plan phase complete while a baseline prerequisite is incomplete.
- Persist new artifacts with a schema version and compatibility tests.
- Use structural facts and evidence IDs as graph, policy, scenario, and comparison inputs.
- Never execute target code during `audit`, `scan`, graph construction, or policy evaluation.
- Run failure scenarios only in the verified disposable execution boundary.
- Use fakes and fixtures by default; live providers and external side effects remain opt-in.
- Keep human, JSON, HTML, and CI summaries consistent with one canonical artifact.
- Treat unknown and not-exercised behavior as first-class results.
- Measure precision, false positives, review burden, latency, seeded failures caught, and
  behavioral change. Do not use generated-file count as evidence of success.

## Completion Records

Each phase document ends with a completion record. Record the revision, delivered behavior,
commands and results, benchmark or usability evidence, known limitations, and deferred work.
“Not started” means design only; it must never be presented as shipped functionality.
