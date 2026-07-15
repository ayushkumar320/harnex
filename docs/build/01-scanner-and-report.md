# Phase 1: Scanner and Audit Report

## Product Outcome

`harness scan <path>` performs a useful, deterministic, read-only audit of a supported Python repository without credentials or target-code execution.

## User Experience Outcome

The user immediately understands what was scanned, what was excluded, what AutoHarness found, and where the detailed report lives. Unknown areas are visible rather than treated as success.

## Scope

- Safe repository-root resolution and read-only `RepositoryView`.
- Gitignore, AutoHarness ignore, binary, generated-file, size, and secret exclusions.
- Python inventory using `ast`; use LibCST only where precise location requires it.
- Detection of Python functions, CLI candidates, direct model call candidates, broad retry loops, and shell/filesystem side-effect candidates.
- Factual `StructuralFact` schema with source evidence and content hashes.
- `AuditReport` schema and human/JSON reporters.
- Initial finding-free scan summary; normalized findings arrive in Phase 3.
- Stable scan exit behavior for invalid, empty, partial, and unsupported repositories.

## Deliverables

- Repository inventory and exclusion report
- Python scanner modules
- Fixture repositories with labeled structural facts
- Canonical JSON artifact under configurable output path
- Human terminal summary
- Performance baseline for small fixtures

## Acceptance Gates

- Scanning never imports fixture packages or executes their hooks.
- Symlinks outside the root are excluded and reported.
- `.env`, keys, and configured secret paths never appear in reports.
- Repeated scans of the same snapshot produce byte-stable canonical JSON except explicitly documented timestamps.
- Human and JSON output contain the same counts and facts.
- Positive and negative fixtures cover every detector.

## Out of Scope

- Model-assisted interpretation
- Documentation retrieval
- Final reliability findings or remediation plans
- Code generation
- Target execution

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Phase 1: the first genuinely useful product behavior.

Operate as:
1. A senior static-analysis engineer who distrusts dynamic execution and designs factual, testable scanners.
2. A product manager proving the audit-first wedge: optimize for evidence quality and honest unsupported results, not detector count.
3. A user advocate: after one command, the developer should feel informed and safe, never overwhelmed or misled.

Before editing:
- Read AGENTS.md completely.
- Read docs/product/vision.md, docs/product/user-experience.md, docs/product/scope.md, docs/architecture/overview.md, and docs/architecture/security.md.
- Read the Phase 0 completion record and run its acceptance commands.
- Inspect current schemas and CLI conventions before extending them.

Build `harness scan <path>` as a read-only deterministic pipeline:
- Resolve and normalize a repository root without following paths outside it.
- Create RepositoryInventory with included files, exclusions, reasons, hashes, language counts, and scan configuration.
- Respect .gitignore plus a documented AutoHarness ignore file. Enforce binary and file-size limits.
- Exclude likely secrets before content reaches scanners. Never include secret contents in verbose output.
- Parse Python files as data. Never import modules, run setup, invoke plugins, or execute tests.
- Emit typed StructuralFact records for functions, imports, call sites, exception/retry structures, CLI candidates, provider-call candidates, shell/process calls, filesystem writes, and unresolved dynamic patterns.
- Include exact relative path, line/column where reliable, detector ID, evidence hash, and confidence basis.
- Emit canonical versioned JSON and a concise Rich terminal summary from the same report model.

Product decisions:
- Prefer a small set of precise detectors over broad low-confidence guessing.
- Clearly distinguish parse failure, excluded file, unsupported syntax, unknown dynamic behavior, and cleanly scanned file.
- A partial scan is not a full success; summarize coverage and use the documented exit contract.
- Do not turn facts into safety findings yet. Phase 3 owns policy findings.

UX requirements:
- State read-only behavior at command start in interactive mode.
- Show repository root, included/excluded counts, parse failures, candidate entry points, model calls, and side-effect candidates.
- Keep the terminal summary within a normal viewport for small repos and point to the detailed artifact.
- Give one next action. Do not ask for an API key.

Security tests:
- setup.py and package import side effects never execute.
- Symlink, .. traversal, absolute path, oversized file, binary content, malicious filename, terminal escape, and secret fixtures.
- Prompt-like text in source is treated as text.

Quality tests:
- Golden JSON fixtures with deliberate schema review.
- Detector unit tests and end-to-end CLI tests.
- Determinism test across repeated runs.
- A basic performance test with enough files to catch accidental quadratic behavior.

Run all Phase 0 and Phase 1 acceptance gates. Update architecture and user docs when implementation decisions differ. Append the Phase Completion Record only when the command provides useful output on at least three fixture repository shapes.
```

## Phase Completion Record

### 2026-07-15

- Delivered `harness scan <path>` as a deterministic, read-only structural scanner for Python
  repositories. The scanner inventories repository files, applies `.gitignore` and
  `.autoharnessignore`, excludes secret paths/content, binary files, oversized files, generated
  cache directories, and symlinks, and never imports or executes target code.
- Added versioned Phase 1 scan schemas: `RepositoryInventory`, `StructuralFact`, `ParseFailure`,
  `ScanSummary`, and `AuditReport`.
- Added AST detectors for functions, imports, call sites, CLI candidates, direct model-call
  candidates, shell/process side effects, filesystem-write side effects, broad exception handlers,
  and unknown dynamic lookup/import patterns.
- Added canonical byte-stable JSON report writing through `--output`, JSON terminal output through
  `--format json`, and a concise human summary from the same report model.
- Added persistent fixture repositories for a basic Python agent, edge-case exclusions/side effects,
  and an unsupported text-only repository, plus tests for no target execution, symlink escape
  exclusion, secret exclusion, deterministic JSON, human/JSON count consistency, parse failures,
  invalid paths, basic performance, and a normalized golden JSON report.
- Acceptance commands run successfully: `uv sync --all-extras --locked`,
  `uv run harness --help`, `uv run harness --version`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest` (25 tests),
  `docker build -t autoharness:phase-0 .`, and
  `docker run --rm autoharness:phase-0 --version`.
- Phase 1 scan smoke commands run successfully on:
  `tests/fixtures/repositories/basic_agent`,
  `tests/fixtures/repositories/edge_cases`, and
  `tests/fixtures/repositories/unsupported_text`.
- Repeated scans of the same fixture produced byte-identical canonical JSON artifacts.
- Known limitations deferred to later phases: no model-assisted interpretation, no retrieval or
  external evidence, no normalized reliability findings, no remediation planning, no generation,
  no target execution, and no sandbox enforcement.
