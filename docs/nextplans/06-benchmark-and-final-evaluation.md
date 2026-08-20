# Next Phase N6: Benchmark and Final-Year Evaluation

## Product Outcome

AgentHarness has a reproducible, held-out evaluation demonstrating what it detects, what it
can safely repair, which failures the repaired system withstands, and where results remain
unsupported or inconclusive.

## Academic Outcome

The final report can defend claims with a labeled corpus, explicit research questions,
controlled comparisons, threats to validity, and repeatable commands rather than screenshots
or generated-file counts.

## Prerequisites

- Build Phase 3 for detection evaluation
- N3 and N4 for repair-effectiveness evaluation when repair claims are included
- N1 for the visual demonstration when included
- N2/N5 when policy or CI claims are included
- Completion records for every feature represented as implemented

## Scope

- Corpus of 10-20 licensed public repositories or purpose-built fixtures.
- Development and held-out splits declared before tuning.
- Ground truth for entry points, model calls, retry boundaries, side effects, secret-flow
  risks, unknown dynamic behavior, expected findings, and seeded runtime failures.
- Seeded scenarios: provider timeout, rate limit, route exhaustion, malformed output,
  timeout after fake commit, duplicate email/refund, logger secret, denied filesystem/network,
  and edited generated file where supported.
- Metrics for fact/finding precision and recall, false positives per KLOC, unknown escalation,
  scan time, memory, provider attempts/tokens, repair success, regression rate, seeded failures
  caught, stable output, and user task completion.
- Ablation comparing deterministic-only audit with bounded LLM-assisted interpretation.
- Small usability study for finding comprehension and risk-graph usefulness.
- Reproducible final demo based on a customer-support or booking agent fixture.

## Initial Evaluation Targets

These are proposed targets to review after a pilot, not claims:

- At least 90% precision on reportable high-severity findings.
- At least 80% recall on the supported labeled finding catalog.
- 100% escalation of labeled unsupported dynamic cases to unknown/unsupported.
- Zero secret leakage in the security fixture suite.
- Zero duplicate committed side effects in the validated idempotency repair scenario.
- Byte-stable canonical deterministic artifacts for unchanged inputs.
- A useful read-only audit of a small fixture in under 30 seconds on the documented machine.
- No live credentials or paid calls required for reproducibility.

If a target is missed, report the measured result and limitation. Do not tune on the held-out
set without declaring a new split.

## Deliverables

- Versioned benchmark manifest and ground-truth schemas
- Corpus license/provenance record and data cards
- Deterministic benchmark runner
- Raw machine-readable results and analysis notebook/script
- Final report chapters: problem, literature/context, design, threat model, implementation,
  experiment, results, limitations, ethics/privacy, and future work
- Demonstration script and failure-recovery transcript
- Support matrix that separates implemented, contract-tested, live-tested, and unsupported

## Acceptance Gates

- Ground truth and held-out split are committed before final detector tuning.
- Metrics distinguish structural detection, LLM interpretation, repair, and verification.
- Every public claim cites a benchmark result and test environment.
- Default reproduction performs no live provider or external side effect.
- Raw results can regenerate every table and chart in the final report.
- Failures and inconclusive results remain in the dataset and report.
- At least one evaluator can reproduce the main experiment from documented commands.

## Threats to Validity to Report

- Purpose-built fixtures may not represent production repositories.
- Static analysis misses reflection, runtime registration, generated code, and dependency
  injection.
- Adapter support may bias results toward known frameworks.
- Seeded failures may simplify real distributed failure.
- LLM outputs vary across models and provider availability.
- Small usability samples cannot establish broad developer adoption.
- Passing sandbox and fixture tests is not proof of production safety.

## Out of Scope

- Claiming universal agent reliability
- Hiding missed targets or unsupported repositories
- Training on held-out examples after inspecting their failures
- Requiring paid services to reproduce core results
- Adding new languages or frameworks to inflate feature count before evaluation

## Detailed Codex Prompt

```text
You are the lead engineer and research evaluator implementing AgentHarness Next Phase N6: benchmark and final-year evaluation.

Act as:
1. A senior empirical software-engineering researcher defining ground truth, held-out evaluation, ablation, and threats to validity.
2. A release engineer making every experiment reproducible without live credentials.
3. A product manager deciding whether measured evidence supports the project's claims.

Before editing:
- Read AGENTS.md, product scope, Build Phase 8, docs/nextplans/README.md, this phase, and every selected feature completion record.
- Inventory actual implemented capabilities. Remove or label any planned-only feature from the experiment and demonstration.
- Freeze research questions, ground-truth schema, corpus provenance, development/held-out split, metrics, and pilot thresholds before tuning.

Build the corpus and runner:
- Create 10-20 licensed public examples or purpose-built fixtures with documented provenance.
- Label facts, findings, unknown behavior, expected support tiers, repair applicability, and scenario invariants.
- Seed provider timeout, rate limit, route exhaustion, malformed output, duplicate side effect, secret-bearing error, denied path/network, and user-edited generated output where supported.
- Implement a deterministic runner that records environment, revision, configuration, adapters, model route, seeds, duration, memory, tokens/attempts, artifacts, and failures.

Evaluate detection:
- Measure fact and finding precision/recall, false positives per KLOC, unknown escalation, coverage, scan time, and memory.
- Compare deterministic-only output with bounded LLM-assisted interpretation using the same evidence and labeled corpus.
- Keep held-out results untouched by subsequent tuning unless a new split is declared.

Evaluate repair and verification:
- For each supported repair family, report applicable cases, generation success, review changes, scenario pass rate, regressions, inconclusive results, exact side-effect counts, latency/attempt tradeoffs, and stable regeneration.
- Never merge semantic quality, security invariants, availability, and maintenance cost into one opaque score.

Evaluate usability:
- Give participants a seeded repository and compare finding comprehension with text-only output versus the risk graph when N1 is implemented.
- Measure time to identify the highest-risk path, correctness, confidence, confusing terminology, and willingness to use audit/check again.
- Obtain appropriate consent and avoid collecting repository secrets or unnecessary personal data.

Produce final artifacts:
- Store raw versioned results and generate all report tables/charts from them.
- Document method, environment, results, missed targets, unsupported cases, threats to validity, and future work.
- Create a deterministic demonstration: audit a support/refund agent, inspect the risk path, approve one supported repair, inject failures, and show the before/after comparison.
- Publish a support matrix separating implemented, contract-tested, live-tested, and unsupported behavior.

Run the full standard, security, benchmark, and clean-room reproduction suites. Append the completion record with the exact corpus version, results, missed targets, limitations, and final project claim.
```

## Phase Completion Record

Not started.
