# Next Phase N2: Reliability Policy as Code

## Product Outcome

Teams can express a small, versioned reliability policy and receive explainable pass, fail,
unknown, and not-applicable results backed by the same evidence as the audit.

## User Problem

Severity defaults cannot represent every repository's risk tolerance. A support chatbot and
a refund agent need different requirements, but policy flexibility must not allow model
output or repository text to create permissions.

## Prerequisites

- Build Phase 3 findings, support tiers, suppressions, and stable exit codes
- Versioned configuration precedence and artifact compatibility
- Optional N1 graph for policy visualization; it is not required for evaluation

## Scope

- Versioned `autoharness-policy.yaml` schema.
- Initial rule families for model timeouts, total attempts, fallback route, raw-content
  logging, secret redaction, side-effect idempotency, unrestricted shell/filesystem tools,
  support-tier minimums, and CI severity thresholds.
- Four-valued evaluation: `pass`, `fail`, `unknown`, `not_applicable`.
- Evidence-backed `PolicyEvaluation` artifact and human output.
- Narrow path/rule scopes, documented overrides, reason, owner, and optional expiry.
- Policy validation and migration behavior.
- `harness policy init`, `harness policy validate`, and audit/check integration.

## Example

```yaml
schema_version: "1.0"

model_calls:
  timeout_required: true
  max_attempts: 3
  fallback_route_required: true

side_effects:
  idempotency_required_for:
    - payment
    - refund
    - booking

privacy:
  raw_prompt_logging: forbidden
  secret_redaction: required

tools:
  unrestricted_shell: forbidden
  unrestricted_filesystem: forbidden

ci:
  fail_on_new_severity: high
  fail_on_unknown_side_effect: true
```

## Deliverables

- Policy schemas, parser, semantic validator, and compatibility tests
- Deterministic evaluator over canonical audit artifacts
- Starter policy with comments explaining tradeoffs
- Policy initialization, validation, and reporting commands
- Override/expiry audit trail
- Positive, negative, unknown, and not-applicable fixtures

## Acceptance Gates

- Policy evaluation never executes target code or calls a model.
- Every `pass` and `fail` names the rule, evaluated facts, and evidence; unknown is never
  coerced to pass.
- Invalid, unsupported, or incompatible policies fail with stable errors and remediation.
- Repository prose and model output cannot alter the selected policy or approve an override.
- Overrides are visible in human and JSON output and require reason plus bounded scope.
- Policy and finding counts remain consistent across audit, check, JSON, and HTML outputs.

## Out of Scope

- A general-purpose programming language for arbitrary organization logic
- Policies that grant sandbox, network, provider, or filesystem permissions
- Automatically generated policy acceptance without human review
- Claiming compliance with external standards without a separate mapping and evidence review

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Next Phase N2: reliability policy as code.

Act as:
1. A senior policy-engine engineer designing versioned, deterministic, explainable evaluation.
2. A product manager keeping the first policy catalog small and tied to observed user risk.
3. A security engineer ensuring policy cannot become a permission-escalation language.

Before editing:
- Read AGENTS.md, product scope, security model, Build Phase 3, this phase, and all prerequisite completion records.
- Inspect current findings, configuration precedence, suppressions, exit codes, and artifacts.
- Write the initial policy rule catalog, applicability rules, and four-valued truth table before coding.

Implement schemas and loading:
- Define versioned Policy, PolicyRule, PolicyScope, PolicyOverride, PolicyEvaluation, and PolicyRuleResult models.
- Parse YAML through Pydantic boundaries, reject duplicate/unknown critical keys, and normalize path scopes safely.
- Preserve compatibility or provide explicit migration diagnostics.
- Keep credentials, provider authorization, sandbox permission, and output roots outside policy authority.

Implement evaluation:
- Evaluate only canonical facts, findings, support tiers, and configured runtime contracts.
- Produce pass, fail, unknown, or not_applicable with evidence, explanation, and remediation.
- Treat missing evidence as unknown where a requirement applies; never convert unknown to pass.
- Add overrides with stable ID, owner, reason, scope, creation time, optional expiry, and report visibility.

UX and commands:
- Implement policy init with a conservative commented starter policy.
- Implement policy validate without scanning a repository.
- Integrate evaluation into audit and check while keeping JSON the source of truth.
- Explain exactly why a command failed and how to narrow or correct a rule.

Testing:
- Test every rule in pass, fail, unknown, and not-applicable states.
- Test invalid schema, expired override, path traversal, symlink-related scopes, prompt-like YAML strings, duplicate keys, incompatible versions, and terminal-control content.
- Assert zero model/network calls and deterministic output.

Run all standard and prerequisite gates. Append the completion record with the shipped rule catalog, compatibility contract, false-positive review, and deferred rules.
```

## Phase Completion Record

Not started.
