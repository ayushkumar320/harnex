# Phase 2: Model Providers, Retrieval, and External Evidence

## Product Outcome

AutoHarness can run its LLM reasoning core through Groq, Hugging Face, or a generic OpenAI-compatible endpoint, combine local documentation with budgeted Tavily evidence, and clearly degrade to structural inventory when no model is available.

## User Experience Outcome

The user knows whether any repository content may leave the machine, sees which provider and model are selected, and receives a clear local-only fallback when credentials, quota, or capability are unavailable.

## Scope

- Local lexical and fuzzy retrieval with source provenance.
- Document collection for README, docs, agent instructions, docstrings, examples, and test descriptions.
- Secret and path filtering before indexing.
- Typed model-provider contract and normalized capabilities, requests, responses, and failures.
- Groq, Hugging Face Inference, and generic OpenAI-compatible adapters.
- `ExternalEvidenceProvider` contract and Tavily Search/Extract adapter.
- Official-domain policy, query privacy, content-addressed web cache, and credit ledger.
- Bounded `EvidenceBundle` combining structural, local, and external evidence for the LLM.
- Disabled, local-only, and remote-allowed data policies.
- Bounded fallback and rate-limit behavior.
- Fake adapters and HTTP contract tests; live tests are opt-in.

## Deliverables

- `RetrievedEvidence` schema
- Local retrieval index and query API
- Provider registry and capability negotiation
- Config validation and provider diagnostics in `harness doctor`
- Provenance in assisted output
- Provider and retrieval security fixtures
- Tavily evidence schemas, cache manifest, and fake adapter

## Acceptance Gates

- Default scan makes zero model or network calls.
- Every remote request can be traced to a previewed, redacted evidence set.
- Missing credentials return a useful diagnostic without breaking deterministic features.
- Provider fallback never violates local-only policy.
- Fake and contract tests cover timeout, rate limit, malformed response, unsupported capability, auth failure, and redaction.
- Prompt injection in indexed docs cannot change provider policy or output paths.
- Tavily never receives private source, repository names, internal hosts, or raw stack traces by default.
- Online enrichment respects a hard per-command credit budget and performs zero calls during verification.
- LLM responses cite valid evidence IDs before candidate findings or plan actions are accepted downstream.

## Out of Scope

- Deterministic acceptance of unsupported or ungrounded model findings
- Automatic semantic eval approval
- Model-generated code application
- Live provider tests in normal CI

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Phase 2.

Work simultaneously as:
1. A senior distributed-systems and LLM-integration engineer who normalizes provider differences, bounded retries, capabilities, privacy, and failure semantics.
2. A product manager committed to an LLM-core, free-first, provider-neutral product. Do not couple the roadmap to a temporary free model, quota, or search allowance.
3. A user privacy and UX advocate. The user must understand what reaches the model, what reaches Tavily, which sources informed the result, and what becomes incomplete when either service is unavailable.

Before editing:
- Read AGENTS.md completely.
- Read docs/architecture/model-providers.md and docs/architecture/security.md in full.
- Read product vision, UX, scope, and the Phase 1 completion record.
- Run all previous acceptance gates and inspect current config, schema, and error boundaries.

Implement local retrieval first:
- Collect only documented file types and public docstrings from the existing RepositoryView.
- Preserve path, heading or symbol, line range, and content hash.
- Apply secret, size, generated-file, and path filters before indexing.
- Build deterministic lexical/fuzzy retrieval. Do not introduce embeddings or a vector database without benchmark evidence.
- Treat retrieved text as quoted untrusted evidence, never instructions.

Implement provider abstraction:
- Define normalized ProviderCapabilities, ModelRequest, ModelResponse, ProviderFailure, and ModelProvider protocol.
- Add adapters for Groq, Hugging Face InferenceClient, and generic OpenAI-compatible endpoints.
- Keep SDK objects and error types inside adapters.
- Probe or configure capabilities such as structured output, tool calls, streaming, token accounting, and context limits.
- Normalize timeout, rate limit, unavailable, auth, invalid request, unsupported capability, and malformed response.
- Respect Retry-After, jitter, attempt limits, and total elapsed budget.

Data policy and UX:
- Assistance is disabled by default.
- Support local_only and remote_allowed policies.
- Before a remote request, make the redacted evidence manifest inspectable in verbose or plan output.
- Never silently fall back to another remote provider.
- `harness doctor` explains missing credentials, unavailable models, unsupported capabilities, and the deterministic fallback.
- Do not promise that any model remains free. Report current provider failures plainly.

Implement Tavily external evidence:
- Read docs/architecture/external-evidence.md completely and implement its schemas before SDK calls.
- Keep Tavily separate from ModelProvider through ExternalEvidenceProvider.
- Start with Search and Extract only. Use basic search, include_answer=false, official-domain allowlists, and a default maximum of three credits per command.
- Build queries from public package/version/symbol identifiers, not arbitrary source or raw LLM text.
- Add cost estimation, actual-credit tracking, deduplication, extraction batching, cache TTL, provenance, redirect validation, and dependency-version invalidation.
- Build bounded EvidenceBundle artifacts that preserve source IDs for LLM citation.
- Add --online and query/credit previews without making web access implicit.

Testing:
- Use fake providers and HTTP mocks for normal tests.
- Add opt-in live markers with strict time/token budgets, but do not require credentials in CI.
- Test secret redaction in docs, exceptions, HTTP bodies, and debug output.
- Test prompt injection, provider fallback policy, cancellation, retry exhaustion, and deterministic retrieval ranking.
- Verify no network call occurs when assistance is disabled or local_only.
- Test Tavily quota exhaustion, cache behavior, domain/redirect rejection, malformed content, prompt injection, private-query rejection, credit limits, and zero calls during verification.

The LLM may produce schema-valid candidate findings in contract tests, but Phase 3 owns deterministic evidence validation and reportable findings. Run all prior and current acceptance gates, update docs and dependency manifests, and append the Phase Completion Record with the exact model, retrieval, and Tavily capabilities actually verified.
```

## Phase Completion Record

Not started.
