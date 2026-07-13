# Phase 4: Constrained Generation

## Product Outcome

`harness apply` can turn an approved plan into a reviewable, deterministic staged diff for verified patterns without overwriting user work.

## User Experience Outcome

The developer feels that AutoHarness is assisting with a code change, not taking over the repository. They see exactly what will change, why, and how to undo it.

## Scope

- Template registry and versioned generation contract.
- Approved output-root and path enforcement.
- Staging directory and diff renderer.
- Plan freshness and adapter compatibility checks.
- Generated file manifest and provenance headers.
- First deterministic generated artifacts: configuration, runner skeleton, JSONL logger interface, and tests for one verified direct-provider fixture.
- Three-way reapplication preserving user edits.
- Atomic application and rollback on failure.

## Deliverables

- `harness apply` preview and confirmation workflow
- `--dry-run` and machine-readable diff summary
- Template and generated-file manifests
- Verified direct-provider generation adapter
- Merge-conflict report and recovery path
- Reproducibility and path-security tests

## Acceptance Gates

- Generation writes only to staging before approval.
- Absolute paths, traversal, and symlink escapes are rejected.
- Same plan and template versions produce the same staged content.
- Stale plans fail before any target write.
- Reapplication preserves compatible user changes or stops with a clear conflict.
- An interrupted apply leaves the repository in its prior state.

## Out of Scope

- Full runtime retry behavior
- Target code execution
- Model-generated source application
- Sandbox enforcement

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Phase 4: the first repository mutation path.

Operate as:
1. A senior developer-tools engineer specializing in deterministic code generation, filesystem safety, merge behavior, and transactional updates.
2. A product manager protecting trust. Generation is a constrained convenience for verified patterns, never the measure of product success.
3. A user advocate. Applying a plan must feel reviewable, reversible, and unsurprising; conflicts should preserve work and explain recovery.

Before editing:
- Read AGENTS.md and all product, architecture, and security references.
- Read prior completion records and run all existing gates.
- Inspect plan schemas, support-tier logic, repository-view path handling, and CLI error conventions.
- Write the first supported generation contract and fixture boundary before implementing templates.

Implement a constrained generation pipeline:
- Accept only a compatible, fresh, approved HarnessPlan.
- Validate scan hash, config hash, adapter versions, template versions, permissions, and output roots.
- Render tested templates into a private staging directory.
- Use deterministic ordering, newlines, formatting, and metadata.
- Record GeneratedFileManifest entries with path, generator version, template version, plan hash, base hash, and content hash.
- Reject absolute paths, traversal, symlink escapes, special files, and outputs not declared by the plan.
- Produce a human diff summary and machine-readable artifact before mutation.
- Require explicit confirmation interactively; require an explicit flag in non-interactive mode.

Apply safely:
- Use atomic replacement where possible and a transaction journal for recovery.
- On reapply, compare previous generated base, current user content, and new generated content.
- Preserve non-conflicting user edits. Stop on conflict and produce a precise report; never choose the generated version silently.
- Implement --dry-run with zero repository writes outside the AutoHarness artifact directory.
- Provide a documented rollback path for the just-applied transaction.

Initial generated slice:
- Support exactly one verified direct-provider fixture shape.
- Generate configuration, an entrypoint wrapper skeleton, a JSONL logging interface, and deterministic smoke tests.
- Keep runtime retry and actual sandbox enforcement for later phases.
- Do not apply model-generated source. Model assistance may draft comments or eval text only when clearly marked and approved.

UX requirements:
- Show purpose-grouped changes, permissions, dependencies, files added/changed, unresolved decisions, and verification command.
- Explain stale plans and conflicts without stack traces.
- Make cancellation and declined approval successful, clean outcomes.

Testing:
- Golden template output and reproducibility.
- Traversal, symlink, unexpected path, special file, stale plan, adapter mismatch, interrupted write, and cancellation.
- Three-way tests for unchanged, user-only change, generator-only change, compatible edits, and conflict.
- End-to-end apply on disposable fixture repos, followed by a clean second apply.

Run all previous and current gates. Update docs with exact generated files and rollback behavior. Append the completion record only after proving no silent overwrite and byte-stable regeneration.
```

## Phase Completion Record

Not started.
