# User Experience

## Desired User Feeling

AutoHarness handles repositories that may contain valuable work and dangerous tools. The emotional experience is therefore part of correctness.

The user should feel:

- **Safe:** the first interaction is read-only and credentials are not required.
- **Oriented:** output distinguishes inspected, skipped, supported, and unknown behavior.
- **Respected:** uncertainty is visible and never disguised as model confidence.
- **In control:** nothing is applied or executed without a clear transition and review.
- **Productive:** the summary is concise and the next action is obvious.

The user should not feel that they must understand AutoHarness internals to trust a result.

## Primary Users

### Prototype developer

Has a working Python agent and wants to understand what is missing before sharing or deploying it. Needs fast setup and explanations without security jargon.

### Maintainer

Owns several agent repositories and wants repeatable CI findings, stable JSON output, and low false-positive rates.

### Security or platform reviewer

Needs source evidence, trust boundaries, capability claims, and proof that verification did not perform uncontrolled side effects.

## Core Journey

### First scan

The user runs:

```bash
harness scan .
```

The command immediately states that it is read-only, identifies the repository root, and summarizes included and excluded files. It finishes with:

- Overall scan status
- Counts by severity and support tier
- The highest-impact findings
- Unsupported areas
- Artifact paths for JSON and detailed reports
- One recommended next command

No API key prompt appears during structural inventory. A full audit explains which configured local or remote LLM it will use before interpretation begins.

When more than one model route is configured, the command previews the ordered, eligible
route and the total time budget. During fallback it reports concise status such as
`groq_fast timed out; trying hf_backup (attempt 2 of 4)`. The final summary shows the provider
that completed the operation and links to attempt provenance. It never implies that a
fallback success was a primary success.

If all routes fail, the command stops waiting at the declared deadline, preserves the
structural inventory, and labels model interpretation and planning incomplete. The next
action distinguishes missing credentials, temporary cooldown, capability mismatch, policy
restriction, and total provider unavailability.

### Reviewing a finding

A finding should answer five questions in this order:

1. What was found?
2. Why does it matter?
3. What source evidence supports it?
4. How certain and supported is the analysis?
5. What can the developer do next?

Example:

```text
AH-R201  Unsafe retry after an unknown side effect                 HIGH

agent/email.py:42 calls send_message() inside a broad retry loop.
AutoHarness cannot prove whether a timed-out call committed the send.

Support: detected     Confidence: 0.91     Generation: blocked
Next: annotate the adapter as idempotent with a stable key, or exclude this call.
```

### Planning changes

`harness plan .` groups changes by purpose rather than file order:

- Instrumentation
- Retry behavior
- Sandbox enforcement
- Eval and verification
- Dependencies and configuration

The plan shows permissions and dependencies before implementation details. Unknown decisions are explicit checkboxes or unresolved entries, not buried warnings.

### Applying changes

Before mutation, the user sees a concise diff summary and the exact files that will change. AutoHarness refuses to continue if the plan is stale or user-edited generated files cannot be merged safely.

After application, the user receives the rollback path and verification command.

### Verification

Verification begins by stating its containment boundary:

```text
Environment: disposable Docker sandbox
Network: denied
Credentials: fixtures only
Target working tree: not writable
```

The final report separates:

- Passed controls
- Failed controls
- Not exercised
- Requires live approval

## CLI Language

- Use direct verbs: `scan`, `plan`, `apply`, `verify`, `doctor`.
- Say `unsupported` instead of `could not magically detect` or vague model language.
- Say `not verified` instead of `safe` when evidence is incomplete.
- Show source paths relative to the scanned repository.
- Keep stable finding and error codes for searchability.
- Use color only to reinforce severity or status; output must remain readable without it.
- Never use animated progress that hides a long or blocked operation.
- Never leave provider waiting unbounded; show the operation deadline and allow immediate
  cancellation.

## Output Modes

Human output is concise and prioritized. Machine output uses a versioned JSON schema.

```bash
harness scan . --format human
harness scan . --format json --output .autoharness/scan.json
```

Both modes represent the same findings. Human output must not invent summaries that are absent from JSON.

## Exit Codes

Initial contract:

| Code | Meaning |
| --- | --- |
| `0` | Command completed and policy threshold passed |
| `1` | Findings exceeded the configured CI threshold |
| `2` | Invalid command or configuration |
| `3` | Repository could not be analyzed, or a scan completed only partially |
| `4` | Plan is stale or requires unresolved approval |
| `5` | Verification or sandbox capability failed |

Phase 1 makes the scan subset of these codes concrete: invalid paths, empty scans, and partial
parse coverage exit with `3` after rendering any available report.

## Performance Expectations

- Show meaningful progress within 300 ms for interactive commands.
- Inventory a small repository without an LLM in a few seconds; report LLM interpretation time separately.
- Cache only when cache validity is explainable.
- Allow cancellation without leaving generated files or running containers behind.
- Summaries should fit a typical terminal viewport; detailed evidence belongs in report files.

## Accessibility and Ergonomics

- Respect `NO_COLOR` and non-interactive terminals.
- Do not rely on color, icons, or Unicode alone to communicate status.
- Wrap text to terminal width while preserving copyable paths and codes.
- Offer `--quiet`, `--verbose`, and machine-readable modes with documented semantics.
- Never print secrets in debug mode.
