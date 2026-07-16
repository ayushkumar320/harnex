# Phase 3: Findings and Planning UX

## Product Outcome

AutoHarness converts structural facts into evidence-backed reliability findings and produces a reviewable plan for verified patterns. This completes the first useful audit-only product milestone.

## User Experience Outcome

The user can answer: what is wrong, why it matters, where the evidence is, how certain the tool is, what is supported, and what to do next. Planning never feels like an irreversible wizard.

## Scope

- Versioned finding catalog and stable IDs.
- Severity, confidence, support tier, generation state, evidence, and remediation.
- Initial rules for missing instrumentation, broad retries, unknown side effects, secret exposure risk, and uncontained tools.
- Support-tier resolution through adapter conformance.
- `harness plan` and versioned `HarnessPlan`.
- Human and JSON output parity.
- CI severity thresholds and stable exit codes.
- LLM evidence synthesis for candidate findings, explanations, remediation, and plans.
- Deterministic evidence-binding, permission, support-tier, and schema validation.

## Deliverables

- Finding-rule engine and catalog documentation
- Golden finding fixtures with labeled ground truth
- `harness scan` finding summary and detail rendering
- `harness plan` with unresolved decisions and no writes
- Scan and plan hash relationship
- CI configuration examples

## Acceptance Gates

- Every finding cites deterministic evidence.
- Every accepted LLM finding cites valid structural or retrieved evidence and passes deterministic policy validation.
- Unsupported and unknown coverage is visible in summary output.
- `plan` rejects stale, partial, or incompatible scan artifacts.
- Plan actions cite findings and declare permissions, files, dependencies, verification, and approval state.
- Exit codes match human and JSON statuses.

## Out of Scope

- Applying plans
- Generating source files
- Runtime retry implementation
- Target-code execution

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Phase 3, the audit-only product milestone.

Act as:
1. A senior static-analysis and policy-engine engineer designing stable, evidence-backed findings and versioned plans.
2. A product manager deciding which findings are genuinely valuable. Favor high precision, clear remediation, and measured support over a large catalog.
3. A CLI UX steward. The user should finish a scan feeling oriented and in control, with uncertainty and unsupported coverage plainly visible.

Before editing:
- Read AGENTS.md, product vision, user experience, scope, architecture overview, security model, and all previous completion records.
- Run previous phase gates and inspect current artifact schemas.
- Define the initial finding catalog in writing before coding it.

Implement LLM-core findings:
- Create a versioned Finding schema with stable ID, title, description, severity, support tier, confidence, generation state, evidence, remediation, and references to detector/adapter versions.
- Implement a small precise catalog and schemas for: uninstrumented model call, broad retry around unknown side effect, unbounded retry, shell or filesystem tool without enforceable boundary, possible secret exposure to retrieval/logging, and unresolved dynamic registration.
- Ask the LLM to synthesize candidate findings from bounded EvidenceBundle inputs and require evidence IDs for every material claim.
- Separate fact collection, LLM reasoning, and deterministic acceptance.
- Derive support tier from verified adapter evidence, not model judgment.
- Make confidence explainable through named factors rather than an opaque model number.
- Add suppression with explicit reason, narrow scope, expiry option, and report visibility. Do not silently hide suppressed findings.

Implement user output:
- Summarize severity, support, coverage, parse failures, exclusions, and highest-impact findings.
- Detail each finding in the order: what, impact, evidence, support/confidence, remediation, next action.
- Emit canonical JSON and ensure terminal counts come from it.
- Add documented CI thresholds and stable exit codes.

Implement `harness plan`:
- Consume a completed compatible scan artifact.
- Produce a versioned HarnessPlan without writing files.
- Every action cites findings and declares adapter, permission, dependencies, output paths, side-effect classification, verification checks, and approval state.
- Block actions for unknown or unsafe findings unless a documented user decision resolves them through a supported contract.
- Hash source scan, config, adapters, and templates needed for later stale-plan detection.

LLM reasoning and guardrails:
- The LLM proposes findings, severity rationale, explanations, remediation, and plan actions.
- Deterministic validators reject nonexistent evidence, unsupported finding IDs, illegal severity values, invalid support claims, expanded paths, unapproved providers, and actions outside adapter capabilities.
- The model cannot approve its own actions, create permissions, or override policy.
- All material text must cite evidence and pass schema, privacy, and redaction checks.

Testing and product validation:
- Use labeled fixture repos to measure initial precision and false positives.
- Golden-test human and JSON outputs while avoiding brittle decoration assertions.
- Test suppression, unknown coverage, stale artifact, incompatible schema, partial scan, CI thresholds, NO_COLOR, and terminal width.
- Conduct at least one manual usability pass from a clean terminal and record confusing output you corrected.

Do not begin generation. Run all gates, update public docs with the real finding catalog and exit contract, and append a completion record including initial measured precision on fixtures.
```

## Phase Completion Record

### 2026-07-15 Initial Deterministic Findings and Plan Slice

- Added the initial public finding catalog in `docs/architecture/finding-catalog.md`.
- Added deterministic findings for uninstrumented model calls, broad exception handlers,
  uncontained shell/filesystem side effects, secret-like exclusions, and unresolved dynamic
  lookup.
- Extended scan artifacts with active finding counts, severity counts, detailed finding records,
  and visible suppression metadata. Suppressed findings remain in JSON and human summaries show
  the suppressed count.
- Added `.autoharness/suppressions.yml` support with explicit rule, optional path, reason, and
  expiry metadata.
- Added `harness scan --fail-on` for CI severity thresholds and exit code `1` when active
  findings meet the threshold.
- Added read-only `harness plan` producing a versioned `HarnessPlan` from completed scan
  artifacts. Plans reject partial scans and never write target files.
- Manual usability pass: `harness scan tests/fixtures/repositories/basic_agent` and
  `harness plan /tmp/autoharness-basic-scan.json` clearly identified read-only behavior,
  finding counts, one high-impact finding, and one review-only unresolved plan action.
- Acceptance commands for this slice passed: `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest` (60 tests).

### 2026-07-16 Phase 3 Completion

- Added a guarded LLM-proposed finding path through the Phase 2 router. Model output is accepted
  only after schema, catalog rule, evidence ID, support-tier, generation-state, and local-path
  validation. The default scan path remains deterministic and does not call a model.
- Added deterministic validation for LLM-proposed plan actions. Accepted actions must cite active
  findings, remain `review_only`, `read_only`, and `unresolved`, use adapters supported by cited
  structural evidence, avoid output files and dependencies, and cite existing structural evidence
  IDs when supplied.
- Documented model-proposed finding and plan acceptance in
  `docs/architecture/finding-catalog.md`.
- Added CI usage examples and the Phase 3 fixture precision snapshot in `docs/development/ci.md`.
- Updated the documentation index, setup guide, README CI command, and README support-tier text.
- Fixture precision measurement on labeled repositories:
  - `basic_agent`: 1 labeled reportable finding, 1 reported, 0 false positives.
  - `edge_cases`: 4 labeled reportable findings, 4 reported, 0 false positives.
  - `unsupported_text`: 0 labeled reportable findings, 0 reported, 0 false positives.
  - Initial fixture precision: `5 / 5 = 1.00`.
- Manual usability pass: `harness scan --fail-on high` writes the JSON artifact before returning
  exit code `1` for high findings; `harness plan` remains read-only and exits `4` for blocked
  plans while preserving the JSON artifact for review.
- Acceptance commands passed:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src`
  - `uv run pytest` (71 tests)
  - `docker build -t autoharness:dev .`
  - `docker run --rm autoharness:dev --help`
- Known limitations deferred to later phases:
  - LLM-assisted finding and plan synthesis is implemented as guarded callable paths, not enabled
    by default CLI scan/plan commands.
  - Planning remains audit-only; Phase 4 owns constrained generation, staging, diffs, and apply.
  - Docker application image checks pass, but target-code sandbox enforcement remains Phase 6.
