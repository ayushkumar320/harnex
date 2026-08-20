# Next Phase N0: One-Command Workflows

## Product Outcome

A new user gets the primary AgentHarness value through `harness audit .`, can request a safe
end-to-end remediation workflow through `harness improve .`, and can run a non-interactive
policy check through `harness check .` without learning internal phase ordering.

## User Problem

The low-level sequence `scan -> plan -> apply -> verify` is useful for automation and
debugging but creates onboarding burden. Users need one obvious entry point while safety
transitions remain explicit.

## Prerequisites

- Build Phase 3 for the complete read-only `audit` workflow.
- Build Phase 4 for mutation inside `improve`.
- Build Phase 7 for verification inside `improve`.
- N2 for policy-aware `check`; before N2, `check` may enforce severity thresholds only.

Do not stub missing stages. A partial implementation advertises exactly which stages it can
orchestrate.

## Scope

- `harness audit <path>` orchestration over inventory, scan, optional model interpretation,
  findings, report generation, and next action.
- `harness improve <path>` orchestration over current audit reuse, plan, staged generation,
  diff review, explicit approval, apply, verification, and rollback guidance.
- `harness check <path>` non-interactive audit and threshold/policy evaluation for CI.
- Versioned `WorkflowRun` artifact with stage status, inputs, artifact hashes, duration,
  completeness, cancellation, and next action.
- Cache and freshness rules that reuse only compatible artifacts.
- One progress renderer that never hides blocking provider, approval, or sandbox states.
- `--until`, `--from-artifact`, `--non-interactive`, `--format`, and `--output` behavior.

## Safety Contract

- `audit` is always read-only with respect to the target repository.
- `improve` does not interpret invocation as approval to modify files or execute target code.
- Diff approval and execution approval remain separate when both are required.
- Non-interactive mutation requires an explicit approval artifact or purpose-specific flag;
  absence is error code `4`, not implicit consent.
- Every stage revalidates artifact schema, repository snapshot, configuration, adapter
  versions, permissions, and freshness.
- Cancellation leaves no applied partial transaction or running verification resource.

## Deliverables

- Three top-level CLI commands with shared typed orchestration
- `WorkflowRun` schema and stage-state machine
- Artifact compatibility and cache-reuse validator
- Human and JSON summaries generated from the same workflow artifact
- End-to-end fixture tests for success, partial completion, cancellation, stale inputs, and
  declined approval
- README onboarding centered on `audit` and `improve`

## Acceptance Gates

- A first-time user can obtain a useful read-only report with one command and no credentials.
- `audit` performs zero target repository writes and zero target-code execution.
- `improve` stops before mutation until exact staged changes are approved.
- A failed or cancelled stage records all completed artifacts and one safe next action.
- Cached results are reused only when snapshot, config, schema, and adapter hashes match.
- Human and JSON output report identical stage and completeness states.
- Low-level commands remain available and produce compatible artifacts.

## Out of Scope

- Hiding unsupported or not-exercised stages behind a success message
- Treating one command as blanket approval
- Background daemon or hosted workflow service
- Automatically accepting semantic eval or repair expectations

## Detailed Codex Prompt

```text
You are the lead engineer implementing AgentHarness Next Phase N0: one-command workflows.

Act as:
1. A senior CLI and workflow engineer designing deterministic state machines, resumable artifacts, cancellation, and failure boundaries.
2. A product manager reducing onboarding friction while preserving the audit-first value proposition.
3. A safety-focused UX engineer ensuring one command never becomes invisible approval for mutation or execution.

Before editing:
- Read AGENTS.md, product vision, user experience, security model, this phase, and every prerequisite completion record.
- Run all prerequisite gates and inspect the real scan, plan, apply, and verify APIs.
- State which stages exist. Do not create placeholder success for an unimplemented stage.

Implement the orchestration contract:
- Define a versioned WorkflowRun and typed stage states: pending, running, completed, incomplete, declined, failed, cancelled, and not_available.
- Implement harness audit as read-only composition of existing inventory, scanning, optional provider routing, findings, and reporting.
- Implement harness improve as composition of fresh audit, plan, staged diff, explicit approval, transactional apply, contained verification, and rollback guidance.
- Implement harness check as non-interactive audit plus configured threshold or policy evaluation.
- Reuse existing component functions rather than invoking CLI commands through subprocesses.
- Record source snapshot, config, schemas, adapters, artifact hashes, stage durations, provider completeness, and next action.

Freshness and recovery:
- Reuse an artifact only when repository snapshot, configuration, schema, adapter, and relevant template versions match.
- On stale data, recompute read-only stages automatically but never restage or reapply mutation without a fresh preview.
- Preserve completed artifact references after failure or cancellation.
- Guarantee cleanup of staging, journals, worktrees, and containers through existing component contracts.

UX:
- Show a concise stage list and current stage without animated output that hides waiting.
- Preview model route and total deadline before remote assistance.
- Before mutation, show exact files and permissions and require approval.
- Before execution, show containment and require any distinct live permission.
- End with outcome, completeness, artifact paths, and exactly one recommended next action.

Testing:
- Test audit with no model, successful fallback, provider exhaustion, parse failure, cancellation, and JSON output.
- Test improve with declined diff, stale plan, conflict, interrupted apply, failed verification, and successful rollback guidance.
- Test non-interactive runs cannot cross approval boundaries accidentally.
- Assert parity with low-level command artifacts and zero target writes during audit.

Run all standard and prerequisite gates. Update public onboarding only after real end-to-end behavior passes. Append the completion record with a transcript of a clean first-use workflow.
```

## Phase Completion Record

Partially delivered on 2026-08-20 (minimum viable subset).

Delivered behavior:

- `harness audit <path>`: read-only scan and plan orchestration. No target-source writes and no
  target-code execution.
- `harness improve <path>`: scan, plan, plan approval, staged preview, apply approval, transactional
  apply, and contained verification. `--yes` covers both approvals, `--skip-verify` records a
  skipped verification stage.
- `harness check <path> --fail-on <severity>`: non-interactive scan plus severity gate, exit `1`
  when the threshold is reached.
- `harness approve <plan>`: records explicit approval on the actions that already satisfy every
  generation constraint. This closed the gap where `build_plan` only emitted `unresolved`
  `review_only` actions, which made `harness apply` unreachable from a real plan.
- Versioned `workflow_run` artifact (`.agentharness/workflow.json`) with per-stage status,
  duration, artifact path, detail, and one next action. Human and JSON output render the same
  artifact.
- Commands call component functions directly; no CLI subprocesses.

Commands and results:

- `pytest -q`: 135 passed, including `tests/test_workflows.py` covering audit read-only behavior,
  check pass/fail thresholds, declined plan approval, declined apply approval, a successful apply,
  and approve accept/decline.
- Manual run on `tests/fixtures/repositories/basic_agent`: `audit` completed, `check --fail-on high`
  exited 1, `improve --yes` applied four generated files and verification passed with the sandbox
  check reported as `not_exercised` on a host without Docker.
- `ruff check`, `ruff format --check`, and `mypy src` pass.

Known limitations and deferred work:

- No artifact cache-reuse or freshness validator; read-only stages always recompute. Freshness is
  still enforced by the underlying scan, plan, and apply checks.
- No `--until`, `--from-artifact`, or `--non-interactive` flags. A non-interactive run without
  `--yes` is treated as a refusal and exits `4`.
- No optional model interpretation stage inside `audit`; the router remains opt-in through the
  low-level commands.
- `check` enforces severity thresholds only; policy evaluation waits for N2.
