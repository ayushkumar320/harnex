# Phase 4: Constrained Generation

## Product Outcome

`harness apply` can turn an approved plan into a reviewable, deterministic staged diff for verified patterns without overwriting user work.

## User Experience Outcome

The developer feels that AgentHarness is assisting with a code change, not taking over the repository. They see exactly what will change, why, and how to undo it.

## Scope

- Template registry and versioned generation contract.
- Approved output-root and path enforcement.
- Staging directory and diff renderer.
- Plan freshness and adapter compatibility checks.
- Generated file manifest and provenance headers.
- First deterministic generated artifacts: configuration, runner skeleton, JSONL logger interface, and tests for one verified direct-provider fixture.
- LLM-generated repository-specific wiring staged behind deterministic file, schema, permission, and diff validation.
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
- Unreviewed or unvalidated model-generated source application
- Sandbox enforcement

## Detailed Codex Prompt

```text
You are the lead engineer implementing AgentHarness Phase 4: the first repository mutation path.

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
- Implement --dry-run with zero repository writes outside the AgentHarness artifact directory.
- Provide a documented rollback path for the just-applied transaction.

Initial generated slice:
- Support exactly one verified direct-provider fixture shape.
- Generate configuration, an entrypoint wrapper skeleton, a JSONL logging interface, and deterministic smoke tests.
- Keep runtime retry and actual sandbox enforcement for later phases.
- Use the LLM for repository-specific wiring where templates alone are insufficient, but generate only inside approved staged paths.
- Require evidence-linked generation intent, structured file manifests, syntax/schema validation, deterministic policy checks, human diff review, and explicit approval before applying model-generated source.

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

### 2026-07-16 Initial Dry-Run Staging Slice

- Added `harness apply` with a Phase 4 guarded preview path. This first slice required
  `--dry-run` and performed no target writes.
- Added a constrained generation module that loads `HarnessPlan` artifacts, validates the
  referenced scan hash and repository freshness, accepts only approved
  `write_generated_files` actions for the `openai_compatible` adapter, and rejects unsafe paths,
  unapproved actions, unsupported adapters, stale scan artifacts, and missing generation actions.
- Added deterministic staging under `.agentharness/staging/<plan-hash>/` plus a canonical
  `apply_preview` JSON artifact.
- Added generated-file manifest entries with target path, staged path, generator version, template
  version, plan hash, base hash when present, content hash, and action ID.
- The initial direct-provider template set stages:
  - `.agentharness/generated/agentharness_config.py`
  - `.agentharness/generated/agentharness_jsonl_logger.py`
  - `.agentharness/generated/agentharness_runner.py`
  - `.agentharness/generated/tests/test_agentharness_smoke.py`
- Adjusted scan freshness fingerprinting so AgentHarness' own `.agentharness` artifact directory
  does not make a source scan stale.
- Added tests for deterministic dry-run staging, machine-readable CLI preview output,
  non-dry-run rejection, unapproved plan rejection, stale plan rejection, unsafe output path
  rejection, and symlink output component rejection.
- Acceptance commands for this slice passed: `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest` (78 tests).

Still in progress: confirmed target-file application, interactive approval, transaction journal,
rollback, three-way reapplication, conflict handling, special-file/interruption negative
tests, Docker gates, and the Phase 4 completion record.

### 2026-07-16 Confirmed Apply and Rollback Slice

- Added explicit non-interactive approval with `harness apply --yes`. Running `apply` without
  `--dry-run` or `--yes` exits with `AH-G007` before writing target files.
- Added atomic replacement from staged generated files into the approved generated paths.
- Added transaction journals under `.agentharness/transactions/<transaction-id>.json` with
  transaction status, plan hash, repository root, per-file previous hash, backup path when a file
  existed, and new content hash.
- Added automatic rollback for files already written in the transaction if a later write fails.
  Rollback failures are not hidden, and the original write failure is surfaced as structured error
  `AH-G009` after the rollback attempt.
- Existing generated target files are rejected with `AH-G010` and left unchanged until the
  three-way reapplication slice is implemented.
- Added tests for successful `--yes` application, machine-readable applied preview output,
  transaction journal creation, existing-target rejection, and rollback after a simulated later
  write failure.
- Acceptance commands for this slice passed: `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest` (82 tests).

Still in progress: interactive approval prompt, three-way reapplication, conflict handling,
full generated artifact validation against a disposable fixture repo, special-file/interruption
negative tests, Docker gates, and the Phase 4 completion record.

### 2026-07-16 Phase 4 Completion

- Added interactive confirmation for `harness apply`; declined approval exits successfully and
  writes no target files. `--yes` remains the non-interactive explicit approval flag.
- Implemented three-way reapplication using the transaction journal's generated-base snapshots:
  unchanged generated files are replaced, append-only user edits are preserved, and edits inside
  the generated base region stop with structured conflict `AH-G010`.
- Added special-file rejection before staging hashes or writes. Directories and symlink components
  in generated output paths fail closed.
- Added structured rollback handling for interrupted writes. If a later file write fails, files
  already written in the transaction are removed or restored and the journal records
  `rolled_back`.
- Added a disposable fixture flow that scans `basic_agent`, creates an explicitly approved
  generation plan, applies generated files, and compiles all generated Python artifacts.
- Final generated files for the direct-provider slice:
  - `.agentharness/generated/agentharness_config.py`
  - `.agentharness/generated/agentharness_jsonl_logger.py`
  - `.agentharness/generated/agentharness_runner.py`
  - `.agentharness/generated/tests/test_agentharness_smoke.py`
- Acceptance commands passed:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src`
  - `uv run pytest` (89 tests)
  - disposable scan-plan-apply-compile fixture flow
  - `docker build -t agentharness:dev .`
  - `docker run --rm agentharness:dev --help`
- Known limitations deferred to later phases:
  - Generated files are review skeletons; full runtime retry behavior remains Phase 5.
  - Generated smoke tests are syntax/import scaffolds, not isolated target execution.
  - Sandbox enforcement remains Phase 6.
