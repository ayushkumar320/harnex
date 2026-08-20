# Finding Catalog

Phase 3 starts with a small deterministic catalog. The catalog favors precise evidence over broad
coverage; unsupported behavior remains visible rather than converted into speculative plans.

| ID | Title | Severity | Support tier | Generation | Evidence source |
| --- | --- | --- | --- | --- | --- |
| `AH-R101` | Model call has no detected reliability instrumentation | high | detected | review_required | `model_call_candidate` structural fact |
| `AH-R102` | Broad exception handler can hide reliability failures | medium | detected | blocked | `broad_exception_handler` structural fact |
| `AH-R103` | Unbounded retry loop can never terminate | high | detected | blocked | `unbounded_retry_loop` structural fact |
| `AH-S101` | Tool side effect has no enforceable boundary | high | detected | blocked | `side_effect_candidate` structural fact |
| `AH-S201` | Secret-like path or content was excluded from scan | medium | detected | blocked | repository exclusion with `secret_path` or `secret_content` |
| `AH-U101` | Dynamic registration or lookup is unresolved | low | detected | blocked | `unknown_dynamic_pattern` structural fact |

## Confidence Factors

Findings do not use opaque confidence. Each finding lists named factors:

- `deterministic_ast_match`: the source location came from Python AST parsing.
- `known_provider_symbol`: the symbol matches a provider-call detector.
- `no_handler_exit`: a `while True` loop retries after an exception handler that never
  breaks, returns, or re-raises.
- `known_side_effect_symbol`: the symbol matches a shell or filesystem side-effect detector.
- `secret_filter_match`: the repository view excluded the path or content through the secret
  filter before retrieval.
- `dynamic_lookup_detected`: the source uses dynamic lookup or import patterns that require
  human review.

## Provider Call Detection

A call is a `model_call_candidate` when either:

- its dotted symbol ends in a provider-only method chain (`.chat.completions.create`,
  `.messages.create`, `.generate_content`, `.converse`, `.invoke_model`, `.text_generation`, and
  the rest of `MODEL_CALL_SUFFIXES`), which matches through any receiver name; or
- its root name is bound by an import in that file *and* the remainder is a known module-level
  generation function (`litellm.completion`, `ollama.chat`, and similar).

The import gate exists because a bare prefix match reports a local variable named `groq` or
`openai` as a provider call. Detection is per-file and syntactic: a provider reached through a
dynamic lookup is reported as `AH-U101`, not as a model call.

## Instrumentation Gate

`AH-R101` reports model calls with *no detected* reliability instrumentation, so a call is only a
finding when no control is visible in scope. A control is a bounding keyword argument
(`timeout`, `max_retries`, `num_retries`, `deadline`, and the rest of `INSTRUMENTATION_KWARGS`) on
the call itself, on any call in the enclosing function, or on a module-level statement such as a
client constructor; or a retry decorator on the enclosing function. Instrumented calls are still
recorded as `model_call_candidate` facts, so the scan summary count stays honest.

The gate detects the *presence* of a control, never its correctness. A `timeout=99999` silences
`AH-R101`.

## Guarded Facts

`StructuralFact.guarded` marks a fact that already has the control its rule asks for, and both
reliability rules skip guarded facts rather than reporting them:

- a `model_call_candidate` is guarded when a bounding keyword argument, a retry decorator, or an
  `agentharness.wrap` call is visible in scope;
- a `side_effect_candidate` is guarded when its enclosing function carries the
  `agentharness.tool` decorator, which declares the side-effect classification the runtime
  enforces.

The flag is syntactic in both directions. It records that a control was declared, never that the
declaration is honest: a function decorated `@tool(side_effect="read_only")` that sends an email
silences `AH-S101` and is a lie the scanner cannot catch.

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
