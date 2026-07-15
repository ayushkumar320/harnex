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
