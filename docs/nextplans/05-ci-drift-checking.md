# Next Phase N5: CI Drift and Pull-Request Checking

## Product Outcome

`harness check .` detects newly introduced, resolved, and unchanged reliability findings or
policy results relative to an approved baseline and produces stable CI output.

## User Problem

A one-time audit loses value as repositories change. Maintainers need to prevent new unsafe
retries, unbounded model calls, secret paths, or unsupported side effects without forcing all
historical debt to block every pull request.

## Prerequisites

- Build Phase 3 stable findings, evidence, suppressions, and exit codes
- N2 policy evaluation for policy-aware enforcement
- Stable repository/config/adapter hashes
- N0 `check` orchestration may be implemented in this phase if not already available

## Scope

- Versioned `AuditBaseline`, `FindingFingerprint`, and `DriftReport` schemas.
- Baseline creation and explicit approval workflow.
- Semantic finding fingerprints based on rule, normalized evidence location, symbol, and
  relevant configuration—not unstable prose or line number alone.
- Classification: `new`, `resolved`, `unchanged`, `changed`, `unmatched`.
- CI thresholds for new severity, new unknown side effects, policy regression, parse/coverage
  regression, and expired override.
- Machine-readable report plus concise plain-text/Markdown summary.
- Example GitHub Actions workflow without requiring a hosted service.

## Safety and Integrity

- A baseline is a comparison reference, not evidence that historical findings are acceptable
  or safe.
- Baseline updates require an explicit command and record author/reason metadata when
  available.
- Untrusted pull-request content cannot modify the selected baseline, CI policy, provider
  authorization, or output destination.
- Forked pull requests run without secrets and default to deterministic scanning.

## Deliverables

- Baseline and drift schemas
- `harness baseline create`, `harness baseline inspect`, and `harness check`
- Finding matching algorithm with explainable match factors
- CI exit behavior and Markdown summary
- GitHub Actions example and generic CI documentation
- Fixtures for moved code, renamed symbols, changed severity, fixed findings, new unknowns,
  shallow clones, and missing baseline

## Acceptance Gates

- The same snapshot compared with its baseline yields zero new/resolved findings.
- A moved but semantically equivalent finding is matched or clearly reported unmatched; it
  is never silently dropped.
- New high-severity or configured unknown behavior produces the documented CI exit code.
- Coverage or parse regression cannot make findings disappear and improve the result.
- Baseline creation/update is explicit and leaves a reviewable artifact diff.
- Fork-safe default CI performs no secret-dependent provider or network call.
- Human, Markdown, and JSON outputs contain the same drift counts and decision.

## Out of Scope

- Hosting a pull-request bot or SaaS control plane
- Automatically accepting baseline changes
- Treating all historical findings as waived
- Fragile matching based only on line number or model-generated wording

## Detailed Codex Prompt

```text
You are the lead engineer implementing AgentHarness Next Phase N5: CI drift and pull-request checking.

Act as:
1. A senior CI and developer-tools engineer designing stable baselines, semantic matching, and actionable exit behavior.
2. A product manager minimizing review noise and avoiding a rollout that blocks teams on historical debt.
3. A security engineer protecting baselines and policies from untrusted pull-request changes and secret exposure.

Before editing:
- Read AGENTS.md, Build Phase 3, N0, N2, this phase, and completion records.
- Inspect finding IDs, evidence locations, suppressions, policy results, hashes, and exit codes.
- Define the fingerprint and matching rules in writing with moved-code and ambiguous examples.

Implement baseline and drift artifacts:
- Define versioned AuditBaseline, FindingFingerprint, BaselineMetadata, DriftEntry, and DriftReport schemas.
- Fingerprint stable rule ID, normalized path/symbol, evidence kind, adapter/detector family, and relevant configuration.
- Never fingerprint generated prose, opaque model confidence, or line number alone.
- Record match factors and ambiguity for every non-exact match.

Implement commands:
- Create and inspect baselines explicitly; never update during check.
- Compare a fresh compatible audit with the selected baseline.
- Classify new, resolved, unchanged, changed, and unmatched findings plus policy and coverage regressions.
- Apply configured thresholds and emit stable exit codes.
- Produce JSON as source of truth and derive terminal and Markdown summaries.

CI security:
- Provide a fork-safe example that uses no provider credentials by default.
- Treat repository-controlled workflow, policy, and baseline changes as reviewable inputs, never authority to access secrets.
- Prevent parse failures, exclusions, or reduced coverage from appearing as resolved findings.

Testing:
- Test identical snapshot, added finding, fixed finding, moved code, renamed symbol, severity change, ambiguous match, expired override, parse regression, missing baseline, incompatible schema, and malicious baseline content.
- Assert deterministic ordering, output parity, and zero default network calls.

Run all standard and prerequisite gates. Append the completion record with matching accuracy on labeled changes, CI examples tested, noise observed, and rollout guidance.
```

## Phase Completion Record

Not started.
