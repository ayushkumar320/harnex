# Phase 7: Verification and Evals

## Product Outcome

`harness verify` proves deterministic harness behaviors in a disposable environment and produces draft semantic evals without pretending that generated expectations are authoritative.

## User Experience Outcome

The user understands what passed, what failed, what was not exercised, and what needs live approval. Verification feels contained and diagnostic, not like launching the agent and hoping.

## Scope

- Disposable verification workspace and sandbox orchestration.
- Versioned verification report.
- Deterministic checks for entrypoint, logs, retry limits, redaction, sandbox denial, and regeneration stability.
- Fault-injection provider and tool fixtures.
- Draft eval generation from documented examples with provenance.
- Approval states for semantic assertions and model-based graders.
- Clear live-operation approval boundary.

## Deliverables

- `harness verify` human and JSON output
- Verification check registry
- Fault-injection framework
- Generated deterministic test suite
- Draft eval schema and review flow
- Cleanup, cancellation, and no-network proofs

## Acceptance Gates

- Verification never mutates the original working tree.
- Default verification uses fixture credentials, fake providers, and denied network.
- Reports separate `passed`, `failed`, `not_exercised`, and `requires_approval`.
- Retry, redaction, duplicate-side-effect, and sandbox controls are exercised through injected failures.
- Semantic evals remain `draft` until a developer approves the oracle.
- Repeated generation and verification produce stable artifacts.

## Out of Scope

- Claiming semantic correctness from non-empty output
- Running production credentials or destructive tools by default
- Full LLM-as-judge platform
- Production monitoring

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Phase 7: isolated verification and trustworthy starter evals.

Act as:
1. A senior test-infrastructure engineer skilled in hermetic environments, fault injection, deterministic assertions, and useful failure reports.
2. A product manager separating evidence from theater. Verification must prove specific controls, not inflate pass counts with weak assertions.
3. A user advocate. The user should understand containment before the run and leave knowing exactly what is proven, untested, or awaiting approval.

Before editing:
- Read AGENTS.md, UX, scope, architecture, security, and prior completion records.
- Run all prior acceptance gates, including sandbox capability tests.
- Inventory every generated control and define how it can be tested deterministically.

Implement verification orchestration:
- Create a disposable worktree/copy and run target imports or execution only through the supported sandbox.
- Use fixture credentials, fake providers, denied network, and explicit writable output paths.
- Define versioned VerificationCheck and VerificationReport schemas.
- Track passed, failed, not_exercised, requires_approval, duration, evidence, containment settings, and cleanup status.
- Support cancellation and guarantee cleanup.

Implement deterministic checks:
- Entrypoint can be invoked through the generated runner using a fixture provider.
- Runtime JSONL matches schema and redacts secrets.
- Controlled transient failure causes bounded retry.
- Timeout after fake commit does not repeat the side effect.
- Denied path and network actions are blocked by the backend.
- Same generation inputs produce no unexpected diff.
- Generated tests are importable and runnable.

Implement eval drafts:
- Derive candidate tasks from documented examples and test descriptions with path/line/hash provenance.
- Generate structure and possible assertions, but mark semantic cases draft.
- Require developer approval for expected concepts, tool use, model graders, or external effects.
- Never treat non_empty_answer as sufficient semantic proof.
- Keep deterministic checks separate from semantic eval scores.

UX:
- Before execution show environment, network, credentials, source-write state, and requested capabilities.
- Summarize results by proven/failed/not exercised/requires approval.
- For a failure, show check, evidence, likely component, containment status, and next action.
- Do not use a single green success label if important checks were not exercised.

Testing:
- End-to-end fixture verification with all deterministic checks.
- Failure, timeout, cancellation, cleanup, malformed log, secret leak, sandbox capability loss, stale plan, and draft approval tests.
- Assert no network or host write in default verification.
- Test stable human/JSON parity and exit codes.

Run all gates and update README examples to match real output. Append the completion record with the exact control claims verification can now support and a list of unverified behavior.
```

## Phase Completion Record

Not started.
