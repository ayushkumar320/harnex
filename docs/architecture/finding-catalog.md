# Finding Catalog

Phase 3 starts with a small deterministic catalog. The catalog favors precise evidence over broad
coverage; unsupported behavior remains visible rather than converted into speculative plans.

| ID | Title | Severity | Support tier | Generation | Evidence source |
| --- | --- | --- | --- | --- | --- |
| `AH-R101` | Model call has no detected reliability instrumentation | high | detected | review_required | `model_call_candidate` structural fact |
| `AH-R102` | Broad exception handler can hide reliability failures | medium | detected | blocked | `broad_exception_handler` structural fact |
| `AH-S101` | Tool side effect has no enforceable boundary | high | detected | blocked | `side_effect_candidate` structural fact |
| `AH-S201` | Secret-like path or content was excluded from scan | medium | detected | blocked | repository exclusion with `secret_path` or `secret_content` |
| `AH-U101` | Dynamic registration or lookup is unresolved | low | detected | blocked | `unknown_dynamic_pattern` structural fact |

## Confidence Factors

Findings do not use opaque confidence. Each finding lists named factors:

- `deterministic_ast_match`: the source location came from Python AST parsing.
- `known_provider_symbol`: the symbol matches a provider-call detector.
- `known_side_effect_symbol`: the symbol matches a shell or filesystem side-effect detector.
- `secret_filter_match`: the repository view excluded the path or content through the secret
  filter before retrieval.
- `dynamic_lookup_detected`: the source uses dynamic lookup or import patterns that require
  human review.

## Planning Rules

`harness plan` is read-only. It produces reviewable actions only for completed compatible scan
artifacts. Actions cite findings and declare permissions, files, dependencies, side-effect
classification, verification checks, and approval state. Unknown, secret, dynamic, and uncontained
tool findings are blocked until a later phase provides verified adapters and user decisions.

## Model-Proposed Finding Acceptance

Phase 3 includes a guarded path for LLM-proposed finding candidates. The model may synthesize
candidate text from bounded structural, local, and external evidence, but acceptance is
deterministic:

- `rule_id` must already exist in this catalog.
- `severity` and `generation` must match the catalog rule.
- `support` must remain `detected`; adapter support is resolved by deterministic evidence, not
  model judgment.
- Every candidate must cite at least one existing structural, local, or external evidence ID.
- Local evidence paths must remain repository-relative and may not use absolute paths or
  traversal.
- Malformed JSON or schema-invalid candidates are rejected before they can become findings.

Accepted model-proposed findings use detector version `phase3.model_findings.v1` and include the
`model_proposed` confidence factor. The default structural scan path remains deterministic and does
not call a model unless model assistance is explicitly invoked by a caller.

## Model-Proposed Plan Acceptance

Phase 3 also defines deterministic validation for LLM-proposed plan actions. Accepted actions must:

- cite active, unsuppressed findings from the source scan artifact;
- remain `review_only`, `read_only`, and `unresolved`;
- declare at least one verification check;
- use an adapter supported by the cited finding's structural evidence;
- avoid output files and new dependencies during the audit-only phase;
- cite only existing structural evidence IDs when evidence is supplied.

The model cannot approve actions, request writes, add dependencies, or expand paths. Phase 4 owns
approved generation and file mutation.
