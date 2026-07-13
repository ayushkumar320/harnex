# Model-Provider Strategy

## Goal

AutoHarness must remain useful without a model and affordable during development. Optional model assistance uses a provider-neutral contract with free-tier and local options first.

No product behavior may assume that a specific model, quota, or free tier will remain available.

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

## Fallback Policy

Fallback is configured, bounded, and visible. It must not silently send repository content to a different provider.

Example:

```yaml
model_assistance:
  enabled: true
  data_policy: remote_allowed
  providers:
    - name: groq
      model: ${AUTOHARNESS_MODEL_NAME}
    - name: huggingface
      model: ${AUTOHARNESS_FALLBACK_MODEL}
  max_provider_attempts: 2
```

A local-only data policy disables remote fallbacks. The final report states which provider received which redacted evidence.

## Retry Policy

Retry only normalized transient failures such as rate limit, timeout before response, or provider unavailability. Respect `Retry-After`, add jitter, cap total elapsed time, and never switch providers after an ambiguous side effect. Model-assistance calls themselves should not have external tool side effects.

Authentication, invalid request, unsupported capability, and policy denial are not retryable.

## Privacy

- Deterministic scan is the default.
- Preview files and evidence eligible for remote assistance.
- Apply secret and path filters before request construction.
- Do not send full repositories.
- Log content hashes and bounded summaries rather than raw content.
- Never print API keys, authorization headers, or provider error bodies without redaction.

## Testing

Default tests use fake adapters and HTTP contract mocks. A separate opt-in test marker may run live provider smoke checks when credentials exist. Live tests do not gate normal pull requests and must use strict token and time budgets.

## Dependency Choice

The bootstrap includes `groq`, `huggingface-hub`, `openai`, and `httpx`. Do not add a broad model-routing framework until measured adapter duplication justifies it; an extra abstraction can obscure provider error and capability semantics that AutoHarness needs to audit accurately.
