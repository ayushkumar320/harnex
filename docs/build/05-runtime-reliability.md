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
You are the lead engineer implementing AutoHarness Phase 5: runtime reliability controls.

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

## Phase Completion Record

Not started.
