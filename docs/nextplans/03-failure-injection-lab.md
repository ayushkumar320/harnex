# Next Phase N3: Failure Injection Lab

## Product Outcome

AutoHarness exercises supported reliability controls against deterministic provider and tool
failures inside the verified execution boundary and reports exactly what behavior was proven.

## User Problem

Static findings and generated tests cannot prove that a timeout, malformed response, or
ambiguous commit behaves correctly. Developers need repeatable failure scenarios without
using production credentials or real side effects.

## Prerequisites

- Build Phase 5 runtime failure taxonomy, retry state machine, and attempt ledger
- Build Phase 6 verified sandbox capability contract
- Build Phase 7 disposable verification and fake provider/tool interfaces

## Scope

- Versioned `FailureScenario`, `FaultStep`, `ExpectedInvariant`, and `ScenarioResult` schemas.
- Deterministic scenario runner using fake clocks, seeded jitter, fake providers, and fake
  side-effect adapters.
- Initial faults: timeout before response, rate limit with `Retry-After`, unavailable
  provider, malformed structured output, authentication failure, timeout after fake commit,
  logger failure, secret in exception, denied path, and denied network.
- Initial invariants: bounded attempts/time, exact committed-operation count, correct fallback
  order, redaction, terminal failure class, ledger consistency, and containment cleanup.
- `harness lab list`, `harness lab run`, and integration with verification.
- Scenario provenance tying each run to finding, repair, adapter, snapshot, and containment.

## Safety Contract

- Default scenarios use no live provider, credential, network, payment, email, booking, or
  other external action.
- Target execution occurs only after the sandbox proves requested capabilities.
- A scenario is unsupported when no verified adapter can inject the fault or observe the
  invariant.
- Live scenarios require a separate design and explicit approval; they are not part of this
  phase's acceptance gates.

## Deliverables

- Scenario catalog and deterministic runner
- Fake provider and fake side-effect adapter conformance suite
- Scenario result artifact and concise terminal summary
- Seeded failure fixture repositories
- Cleanup and containment evidence
- Documentation for authoring adapter-owned scenarios

## Acceptance Gates

- Timeout-before-response triggers only the configured bounded retry/fallback path.
- Timeout-after-fake-commit results in exactly one commit and
  `commit_status_unknown` where status cannot be recovered.
- Secret-bearing failures produce no secret in logs, terminal output, or result artifacts.
- Denied path and network scenarios are blocked by proven sandbox capabilities.
- Repeated scenarios with the same seed and inputs produce stable semantic results.
- Unsupported injection or observation is reported as `not_exercised`, never passed.
- Success, failure, timeout, and cancellation clean up all disposable resources.

## Out of Scope

- Chaos testing production systems
- Live destructive tools or credentials
- Proving semantic answer quality
- Arbitrary monkey-patching of unsupported repositories
- Claiming a passing scenario proves general production safety

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Next Phase N3: Failure Injection Lab.

Act as:
1. A senior reliability-test engineer specializing in deterministic fault injection, distributed failure, and exact invariants.
2. A sandbox engineer who refuses to execute when containment cannot be proven.
3. A product and research engineer producing reproducible evidence rather than theatrical pass counts.

Before editing:
- Read AGENTS.md, security model, Build Phases 5-7, this phase, and all prerequisite completion records.
- Run provider/tool fake conformance and sandbox capability gates.
- Define the scenario catalog, observation points, and expected invariants before implementing orchestration.

Implement scenario models and registry:
- Define versioned FailureScenario, FaultStep, FaultTrigger, ExpectedInvariant, ScenarioRun, Observation, and ScenarioResult schemas.
- Make scenarios adapter-owned and declare required injection, observation, provider, tool, and sandbox capabilities.
- Reject scenarios whose requirements cannot be proven before target execution.
- Hash snapshot, generated harness, scenario, adapters, seed, and containment policy.

Implement deterministic execution:
- Use fake providers, fake side effects, fixture credentials, fake monotonic clocks, and seeded jitter by default.
- Inject timeout before response, rate limit, unavailable provider, malformed output, auth failure, timeout after fake commit, logger I/O failure, hostile secret-bearing errors, denied path, and denied network.
- Observe exact attempt order, elapsed budget, fallback, ledger transitions, commit count, redaction, terminal status, and cleanup.
- Never infer a pass from process exit code alone.

UX:
- Implement lab list and lab run with requested capability preview.
- Show containment, injected fault, expected invariants, observed values, and pass/fail/not_exercised.
- Link every scenario to findings or controls it evaluates.

Testing:
- Unit-test trigger timing and invariant evaluation with fake clocks.
- Contract-test every fake adapter and negative capability path.
- End-to-end test scenario success, violated invariant, unsupported injection, timeout, cancellation, secret error, and cleanup.
- Assert zero live network and exact committed-operation counts.

Run all prerequisite and standard gates. Append the completion record with the scenario catalog, reproducibility evidence, containment results, and behaviors still not observable.
```

## Phase Completion Record

Not started.
