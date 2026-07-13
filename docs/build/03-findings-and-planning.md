# Phase 3: Findings and Planning UX

## Product Outcome

AutoHarness converts structural facts into evidence-backed reliability findings and produces a reviewable plan for verified patterns. This completes the first useful audit-only product milestone.

## User Experience Outcome

The user can answer: what is wrong, why it matters, where the evidence is, how certain the tool is, what is supported, and what to do next. Planning never feels like an irreversible wizard.

## Scope

- Versioned finding catalog and stable IDs.
- Severity, confidence, support tier, generation state, evidence, and remediation.
- Initial rules for missing instrumentation, broad retries, unknown side effects, secret exposure risk, and uncontained tools.
- Support-tier resolution through adapter conformance.
- `harness plan` and versioned `HarnessPlan`.
- Human and JSON output parity.
- CI severity thresholds and stable exit codes.
- Optional model-assisted explanations that cannot create or approve findings.

## Deliverables

- Finding-rule engine and catalog documentation
- Golden finding fixtures with labeled ground truth
- `harness scan` finding summary and detail rendering
- `harness plan` with unresolved decisions and no writes
- Scan and plan hash relationship
- CI configuration examples

## Acceptance Gates

- Every finding cites deterministic evidence.
- Model assistance changes wording only, never finding identity, severity, support, or legality.
- Unsupported and unknown coverage is visible in summary output.
- `plan` rejects stale, partial, or incompatible scan artifacts.
- Plan actions cite findings and declare permissions, files, dependencies, verification, and approval state.
- Exit codes match human and JSON statuses.

## Out of Scope

- Applying plans
- Generating source files
- Runtime retry implementation
- Target-code execution

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Phase 3, the audit-only product milestone.

Act as:
1. A senior static-analysis and policy-engine engineer designing stable, evidence-backed findings and versioned plans.
2. A product manager deciding which findings are genuinely valuable. Favor high precision, clear remediation, and measured support over a large catalog.
3. A CLI UX steward. The user should finish a scan feeling oriented and in control, with uncertainty and unsupported coverage plainly visible.

Before editing:
- Read AGENTS.md, product vision, user experience, scope, architecture overview, security model, and all previous completion records.
- Run previous phase gates and inspect current artifact schemas.
- Define the initial finding catalog in writing before coding it.

Implement findings:
- Create a versioned Finding schema with stable ID, title, description, severity, support tier, confidence, generation state, evidence, remediation, and references to detector/adapter versions.
- Implement a small precise catalog: uninstrumented model call, broad retry around unknown side effect, unbounded retry, shell or filesystem tool without enforceable boundary, possible secret exposure to retrieval/logging, and unresolved dynamic registration.
- Separate fact collection from policy evaluation.
- Derive support tier from verified adapter evidence, not model judgment.
- Make confidence explainable through named factors rather than an opaque model number.
- Add suppression with explicit reason, narrow scope, expiry option, and report visibility. Do not silently hide suppressed findings.

Implement user output:
- Summarize severity, support, coverage, parse failures, exclusions, and highest-impact findings.
- Detail each finding in the order: what, impact, evidence, support/confidence, remediation, next action.
- Emit canonical JSON and ensure terminal counts come from it.
- Add documented CI thresholds and stable exit codes.

Implement `harness plan`:
- Consume a completed compatible scan artifact.
- Produce a versioned HarnessPlan without writing files.
- Every action cites findings and declares adapter, permission, dependencies, output paths, side-effect classification, verification checks, and approval state.
- Block actions for unknown or unsafe findings unless a documented user decision resolves them through a supported contract.
- Hash source scan, config, adapters, and templates needed for later stale-plan detection.

Model assistance:
- May summarize evidence or draft remediation wording.
- Cannot create or remove findings, change severity/support, approve actions, expand paths, or enable providers.
- Assisted text must cite retrieved evidence and pass schema and redaction checks.

Testing and product validation:
- Use labeled fixture repos to measure initial precision and false positives.
- Golden-test human and JSON outputs while avoiding brittle decoration assertions.
- Test suppression, unknown coverage, stale artifact, incompatible schema, partial scan, CI thresholds, NO_COLOR, and terminal width.
- Conduct at least one manual usability pass from a clean terminal and record confusing output you corrected.

Do not begin generation. Run all gates, update public docs with the real finding catalog and exit contract, and append a completion record including initial measured precision on fixtures.
```

## Phase Completion Record

Not started.
