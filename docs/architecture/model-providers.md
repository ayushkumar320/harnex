# Model-Provider Strategy

## Goal

AgentHarness is LLM-core for interpretation, planning, and repository-specific generation. The provider layer makes that reasoning portable across free-tier, local, and hosted models while deterministic guardrails preserve safety and artifact validity.

No product behavior may assume that a specific model, quota, or free tier will remain available. When no model is reachable, AgentHarness may emit a structural inventory, but it must label the full audit and plan as incomplete.

## Initial Providers

### Groq

Use the Groq SDK or its mostly OpenAI-compatible endpoint through the provider adapter. Normalize rate limits, timeouts, token usage, model errors, and unsupported parameters before they reach planning logic.

### Hugging Face Inference

Use `huggingface_hub.InferenceClient` for hosted providers or compatible local endpoints. The adapter must handle model cold starts, unavailable models, timeouts, and provider-specific capability differences.

### Generic OpenAI-compatible endpoint

Support a configurable base URL for local or hosted services. Compatibility is capability-tested; the label "OpenAI-compatible" is not proof that tools, JSON schema, usage fields, or streaming behave identically.

## Internal Contract

```python
class ModelProvider:
    async def capabilities(self) -> ProviderCapabilities: ...
    async def complete(self, request: ModelRequest) -> ModelResponse: ...
    def classify_error(self, error: Exception) -> ProviderFailure: ...
```

Normalized requests contain messages, model, bounded token budget, temperature, optional JSON schema, and trace metadata. They never contain provider SDK clients.

Normalized responses contain content, structured data when requested, finish reason, latency, token usage when available, provider request ID, and redaction-safe metadata.

## Capability Negotiation

Capabilities may include:

- Chat completion
- Structured JSON output
- JSON-schema enforcement
- Tool calls
- Streaming
- Seed support
- Token accounting
- Maximum context and output limits

The planner requests capabilities, not provider names. Missing capabilities cause a fallback, reduced feature, or explicit unsupported result.

Tavily is not part of this provider fallback chain. It implements the separate `ExternalEvidenceProvider` contract described in [External Evidence Architecture](external-evidence.md).

## Routing and Fallback Contract

AgentHarness does not have a hard-coded primary provider. Groq is one adapter in an
ordered, user-approved route. Provider order is configuration, and an installation is
valid when Groq is absent or unavailable.

The router operates in these layers:

1. **Deterministic preparation:** build and validate one redacted evidence manifest before
   any provider call. This layer always remains available.
2. **Primary attempt:** select the first healthy route entry allowed by the data policy and
   capable of the requested operation.
3. **Same-provider recovery:** make at most one additional attempt only for an eligible
   transient failure and only when its delay fits the remaining operation deadline.
4. **Provider failover:** move to the next pre-authorized, healthy route entry. Reuse the
   same evidence-manifest hash; apply the destination's context and output limits before
   sending it.
5. **Approved capability reduction:** when the operation permits it, use a route that lacks
   native schema enforcement and validate bounded JSON locally. This is a distinct result
   mode and never applies to a capability marked required.
6. **No-model completion:** emit the deterministic structural inventory and mark LLM
   interpretation, findings synthesis, and planning `incomplete_model_unavailable`.

Layers 4 and 5 may send data only to destinations already listed in configuration. The CLI
previews the ordered route and eligible evidence before the operation. AgentHarness never
discovers a new remote destination at runtime, silently broadens `local_only`, or treats the
no-model result as a full audit.

Example:

```yaml
model_assistance:
  enabled: true
  data_policy: remote_allowed
  route:
    # A local OpenAI-compatible service can be first, last, or omitted.
    - id: local
      provider: openai_compatible
      base_url: http://127.0.0.1:11434/v1
      model: ${AGENTHARNESS_LOCAL_MODEL}
      locality: local
    - id: groq_fast
      provider: groq
      model: ${AGENTHARNESS_GROQ_MODEL}
      locality: remote
    - id: hf_backup
      provider: huggingface
      model: ${AGENTHARNESS_HF_MODEL}
      locality: remote
  deadlines:
    attempt_seconds: 8
    operation_seconds: 45
  max_attempts_per_provider: 2
  max_total_attempts: 4
  cooldown_seconds: 60
  allow_capability_reduction: true
```

The numeric values are conservative defaults to validate in Phase 2, not availability
promises. Configuration rejects an empty route when model assistance is required, duplicate
route IDs, a local URL labeled remote (or the reverse), non-positive budgets, or a total
attempt count that cannot fit the declared operation deadline.

### Eligibility and selection

Before every attempt, the router filters route entries by:

- data policy and destination locality;
- configured credentials and endpoint validity;
- requested capability and context/output limits;
- command-wide token, attempt, and elapsed-time budgets;
- circuit state from recent normalized failures; and
- cancellation state.

Selection is stable: the first eligible entry in configuration order wins. No latency race
or speculative parallel request sends the same repository evidence to multiple providers.
If an endpoint is in cooldown, the router skips it for the current operation and records the
reason. `harness doctor` can probe it separately without repository evidence.

### Failure routing matrix

| Normalized failure | Retry same provider | Try next approved provider | Notes |
| --- | --- | --- | --- |
| `timeout_before_response` | Once, if budget remains | Yes | Open the circuit after the configured threshold |
| `rate_limited` | Only when `Retry-After` fits | Yes | Do not wait past the operation deadline |
| `provider_unavailable` | Once, if the delay is bounded | Yes | Cool down repeated failures |
| `malformed_response` | One bounded correction when allowed | Yes | Never accept unvalidated output |
| `unsupported_capability` | No | Yes | Reduced mode only when the request permits it |
| `authentication_failed` | No | Yes | Mark only that route unavailable; redact details |
| `invalid_request` | No | No by default | Usually a caller defect shared by providers |
| `policy_denied` | No | No | A fallback cannot weaken policy |
| `cancelled` | No | No | Preserve cancellation immediately |

Provider failover is distinct from runtime retry around target tools. Model-assistance calls
must not perform external tool side effects. If a future provider operation can have an
ambiguous external commit, provider switching is prohibited and the operation ends with
`commit_status_unknown`.

### Deadline and circuit-breaker behavior

Every attempt has a timeout and every logical model operation has one monotonic elapsed-time
deadline. Backoff, `Retry-After`, capability probing, and provider calls all consume that
same deadline. Starting an attempt that cannot fit the remaining minimum budget is forbidden.

The router maintains a bounded, non-secret health record keyed by route ID: normalized
failure class, consecutive transient failures, and cooldown expiry. Authentication failures
remain unavailable until configuration changes or `doctor` confirms recovery. Health state
is advisory for ordering, never authority to bypass policy.

The system cannot guarantee that external services never time out. It guarantees that one
slow provider cannot consume unbounded time, Groq is never a mandatory dependency, and the
terminal result explains every attempted, skipped, failed, and degraded layer.

## Result Provenance

The canonical assisted-operation artifact records:

- requested and delivered capability mode;
- ordered configured route with secret fields omitted;
- every attempt's route ID, provider, model, latency, and normalized result;
- evidence-manifest hash sent on each attempt;
- retry, skip, cooldown, fallback, and reduction reasons;
- final completeness state and unperformed reasoning stages.

Human output summarizes the same artifact. A successful fallback is visible, not presented
as if the primary provider succeeded.

## Privacy

- Deterministic scan is the default.
- Preview files and evidence eligible for remote assistance.
- Apply secret and path filters before request construction.
- Do not send full repositories.
- Log content hashes and bounded summaries rather than raw content.
- Never print API keys, authorization headers, or provider error bodies without redaction.

## Testing

Default tests use fake adapters and HTTP contract mocks. A separate opt-in test marker may run live provider smoke checks when credentials exist. Live tests do not gate normal pull requests and must use strict token and time budgets.

Router tests use a fake monotonic clock and seeded jitter. Required cases include Groq
timeout followed by Hugging Face success, Groq authentication failure followed by local
success, local-only rejection of all remote entries, circuit-open skipping, `Retry-After`
larger than the remaining deadline, capability reduction, cancellation, total exhaustion,
and the final structural-only completeness state. Tests assert exact attempt order and prove
that unapproved destinations receive zero requests.

## Dependency Choice

The bootstrap includes `groq`, `huggingface-hub`, `openai`, and `httpx`. Do not add a broad model-routing framework until measured adapter duplication justifies it; an extra abstraction can obscure provider error and capability semantics that AgentHarness needs to audit accurately.
