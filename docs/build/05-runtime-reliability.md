# Phase 5: Runtime Reliability

## Product Outcome

Generated harnesses provide structured runtime evidence and bounded provider retries without duplicating unknown side effects.

## User Experience Outcome

When a run fails, the developer can tell whether the provider, model response, tool, policy, or application caused it. Retry behavior is visible and predictable rather than mysterious.

## Scope

- Versioned runtime event schema and JSONL writer.
- Redaction, bounded fields, run and operation identifiers.
- Normalized provider and tool failure taxonomy.
- Retry state machine with elapsed-time budget, jitter, and `Retry-After`.
- Side-effect classification and attempt ledger.
- Failure-context packet for model correction before side effects.
- Generated runtime adapters for the verified direct-provider fixture.
- Fault-injection tests before and after fake commits.

## Deliverables

- Runtime logging templates and readers
- Failure classifier and retry policy
- Attempt ledger and `commit_status_unknown`
- Generated tests and human failure summary
- Metrics for attempts, latency, tokens when available, and terminal status

## Acceptance Gates

- No automatic retry occurs for `unknown` or `non_idempotent` operations.
- A timeout after a fake commit produces `commit_status_unknown` and one committed operation.
- Rate limits respect bounded attempts and total elapsed budget.
- Logs remain valid JSONL under logger failure and hostile content.
- Secrets and raw prompt/output content are absent by default.
- Generated runtime behavior is deterministic under fake clocks and seeded jitter.

## Out of Scope

- General workflow checkpointing
- Database transactions
- Browser or network tool isolation
- Production observability backend
- Automatic semantic quality grading

## Detailed Codex Prompt

```text
You are the lead engineer implementing AgentHarness Phase 5: runtime reliability controls.

Act as:
1. A senior reliability engineer who understands distributed failure, idempotency, ambiguous commit state, retry budgets, structured telemetry, and failure injection.
2. A product manager focused on debuggability rather than a misleading success-rate improvement. A stopped duplicate side effect is more valuable than an extra retry.
3. A user advocate. Failure output should reduce anxiety by explaining what failed, what was retried, what was not retried, and what remains unknown.

Before editing:
- Read AGENTS.md, security model, architecture overview, provider strategy, UX, and prior completion records.
- Run all previous gates and inspect the generated runtime boundaries from Phase 4.
- Define the runtime event and failure schemas before writing retry code.

Implement structured runtime evidence:
- Versioned JSONL RuntimeEvent types for run, model call, tool call, retry, policy block, and finish.
- Stable run_id, operation_id, attempt, timestamps, duration, provider/model, normalized status, and token usage when available.
- Redact before serialization. Raw prompts, outputs, headers, environment values, and provider bodies are off by default.
- Bound field sizes and safely render hostile terminal content.
- Logging failures must not produce unredacted fallback output or corrupt the target operation.

Implement failure normalization and retry:
- Normalize timeout-before-response, rate limit, unavailable, malformed structured output, auth, invalid request, policy denial, tool failure, and unknown commit state.
- Use a deterministic retry state machine with max attempts, total elapsed budget, exponential backoff, jitter, and Retry-After.
- Inject clock and random sources for tests.
- Classify operations as read_only, idempotent, transactional, non_idempotent, or unknown.
- Require stable idempotency evidence for idempotent writes.
- Record an attempt ledger before and after every eligible operation.
- If a failure occurs after an unknown side effect may have committed, stop with commit_status_unknown. Never ask the model to repeat the operation.

Retry with context:
- Allow a compact structured failure packet for malformed model/tool output only before an external side effect.
- Preserve the user's goal and avoid dumping full traces into prompts.
- Cap correction attempts and token budget.

Product and UX:
- Human failures summarize cause, attempts, elapsed time, side-effect state, evidence artifact, and next action.
- Do not celebrate retries as success; expose them as reliability events.
- Make partial and unknown outcomes first-class terminal states.

Testing:
- Fault inject timeout before execution, timeout after fake commit, rate limit with Retry-After, malformed output, auth failure, cancellation, retry exhaustion, logger I/O failure, and hostile content.
- Assert exact commit counts and attempt ledger state.
- Assert secrets never appear in JSONL or terminal output.
- End-to-end generate and run the verified fixture using fake providers only.

Run all phase gates and update runtime/security docs. Append the completion record with fault-injection evidence and any operation classes still unsupported.
```

## Phase Progress Record

### 2026-07-16 Initial Runtime Core Slice

- Added `src/agentharness/runtime.py` with versioned `RuntimeEvent` JSONL payloads, normalized
  runtime statuses and failure kinds, side-effect classifications, attempt ledger entries, and a
  deterministic retry executor with injected clock and random source.
- Runtime JSONL writing redacts prompt/raw/header/env/secret-like keys and secret-like values,
  bounds string fields, preserves valid JSON Lines for hostile terminal-control content, and
  records logger write failures without raising or printing unredacted fallback output.
- Retry behavior now has a reusable state machine for read-only and idempotent operations. Unknown
  and non-idempotent operations are not automatically retried, idempotent operations require a
  stable key, and a timeout after a fake unknown-side-effect commit terminates as
  `commit_status_unknown`.
- Added `tests/test_runtime.py` fault-injection coverage for no retry after unknown fake commit,
  no retry for non-idempotent operations, `Retry-After` bounded by total elapsed budget, missing
  idempotency key policy blocking, seeded jitter, JSONL redaction and field bounds, and logger I/O
  failure.
- Acceptance commands passed:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src`
  - `uv run pytest` (96 tests)

Still in progress: generated direct-provider runtime adapter wiring, human failure summaries,
malformed-output correction packets before side effects, generated fixture execution with fake
providers, and the final Phase 5 completion record.

### 2026-07-16 Generated Runtime Adapter Slice

- Added cancellation as a normalized runtime failure that is never retried automatically.
- Added compact `failure_context` packets for malformed structured output only when the operation
  is still before an external side effect. Packets preserve the user goal as a bounded redacted
  summary and avoid raw provider output.
- Added `HumanFailureSummary` output with terminal status, cause, attempts, elapsed time,
  side-effect state, evidence artifact path, and a next action.
- Updated the constrained direct-provider templates to generate:
  - `.agentharness/generated/agentharness_config.py` with runtime retry policy defaults.
  - `.agentharness/generated/agentharness_jsonl_logger.py` with redacted JSONL write/read helpers.
  - `.agentharness/generated/agentharness_runner.py` with a fake-provider-friendly
    `run_direct_provider` wrapper that logs run/model/retry/finish events, applies bounded
    read-only retries, returns a human summary, and emits a correction packet for malformed output.
  - `.agentharness/generated/tests/test_agentharness_smoke.py` with generated fake-provider tests
    for rate-limit retry and malformed-output correction.
- Added repository tests that apply the generated files, import the generated runner, execute it
  against fake providers, assert deterministic retry sleeps, validate redacted JSONL evidence, and
  assert correction-packet contents.
- Acceptance commands passed:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src`
  - `uv run pytest` (102 tests)
- Docker acceptance is still pending because `docker build -t agentharness:dev .` failed before
  build start: the Docker daemon socket did not exist at
  `/Users/ayush/.docker/run/docker.sock`.

Still pending before the final Phase 5 completion record: rerun the Docker build and
`docker run --rm agentharness:dev --help` after Docker is available.

### 2026-07-17 Phase 5 Completion

- Re-ran the full local quality gate after the Docker daemon became available.
- Confirmed the AgentHarness application image builds and starts as a non-root CLI package image.
- Acceptance commands passed:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src`
  - `uv run pytest` (102 tests)
  - `docker build -t agentharness:dev .`
  - `docker run --rm agentharness:dev --help`
- Known limitations:
  - Runtime reliability covers the generated direct-provider fixture and deterministic fake
    providers. Broader framework adapters remain later-phase work.
  - Runtime events and retry policy are not a sandbox boundary; Phase 6 adds capability-tested
    containment for constrained execution.
- Deferred decisions:
  - Production observability exporters, workflow checkpointing, and live semantic evals remain
    out of scope until later phases.
