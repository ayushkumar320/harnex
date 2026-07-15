# Current Phase

We are building [Phase 2: Providers and evidence](02-provider-and-retrieval.md).

Current status: Phase 2 is in progress, not complete.

Completed slices:

- Local retrieval over docs and docstrings.
- Provider/router contracts, fake providers, and `harness doctor`.
- Provider adapter boundaries.
- Tavily/search/extract/cache scaffolding with fake clients.
- Router provenance and citation validation.
- `harness scan --online` local evidence bundle.

Remaining before Phase 2 completion:

- Real Groq, Hugging Face, OpenAI-compatible, and Tavily wiring from config/env.
- HTTP contract tests/mocks for provider and Tavily behavior.
- Circuit persistence and richer provider diagnostics.
- External evidence cache integration into `scan --online`.
- Final Phase 2 acceptance gates and completion record.

Note: the latest `scan --online` evidence-bundle slice may still be uncommitted.

This pointer is intentionally simple. Update it when work moves to the next phase.
