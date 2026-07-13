# Phase 8: Benchmark and Public Alpha

## Product Outcome

AutoHarness reaches a public alpha with measured detection quality, reproducible installation, honest support claims, and a benchmark corpus that can guide future adapters.

## User Experience Outcome

A new user can install, scan a supported repository, understand the result, and decide whether to plan changes without insider knowledge. Public claims match measured behavior.

## Scope

- Benchmark corpus with labeled facts, findings, and seeded failures.
- Held-out repositories not used during detector development.
- Precision, recall, false positives, review burden, speed, memory, and model-cost reporting.
- Cross-platform application image and package release workflow.
- SBOM, dependency review, provenance, and release notes.
- Alpha support matrix and known limitations.
- Installation and first-run usability pass.
- CI examples and migration/version policy.

## Deliverables

- `autoharness-bench` fixtures or clearly licensed benchmark location
- Machine-readable benchmark results and concise report
- Public support matrix
- Locked and reproducible UV environment
- Published package/container release workflow in dry-run or approved registry
- Alpha README, changelog, and security reporting instructions

## Acceptance Gates

- Benchmark includes held-out repositories and negative cases.
- Metrics distinguish detector precision/recall from generation and verification success.
- Public claims cite measured results and test environment.
- Package installs in a clean Python 3.12 environment.
- Container builds reproducibly and runs as non-root.
- Structural inventory works without credentials; full audit works with at least one documented free-tier or local model configuration.
- No known critical security failure remains in supported capability tests.

## Out of Scope

- Declaring general availability
- Expanding to TypeScript before metrics justify it
- Paid hosted service or billing
- Enterprise identity, dashboard, or multi-tenant execution

## Detailed Codex Prompt

```text
You are the lead engineer and release owner implementing AutoHarness Phase 8: benchmark and public alpha.

Operate as:
1. A senior release, quality, and developer-tools engineer who values reproducibility, held-out evaluation, supply-chain integrity, and observable limitations.
2. A product manager deciding whether the product has earned an alpha. Replace aspirational claims with measurements and resist adding features to hide weak metrics.
3. A first-time user advocate. Installation, the first scan, error recovery, and documentation must work for someone who did not build the project.

Before editing:
- Read AGENTS.md and the entire documentation index.
- Review every phase completion record and rerun the full acceptance suite.
- Inventory all public claims, support tiers, schemas, exit codes, generated files, provider capabilities, and sandbox capabilities.
- Define benchmark ground truth and held-out split before tuning detectors.

Build the benchmark:
- Include 10-20 small licensed public repos or purpose-built fixtures, with several held out from detector development.
- Label entry points, provider calls, side effects, retry boundaries, unknown dynamic behavior, and expected findings.
- Seed provider timeout before response, timeout after fake commit, rate limit, malformed output, broad retry, path traversal, symlink escape, secret in docs, prompt injection, dynamic tool registration, and edited generated file.
- Measure fact and finding precision/recall, false positives per KLOC, unknown escalation accuracy, scan time, memory, plan corrections, generation success, seeded failures caught, model calls/tokens/cost, and stable diff rate.
- Publish machine-readable raw results and a concise methodology. Never tune on the held-out set after viewing failures without documenting a new evaluation split.

Prepare the alpha:
- Lock dependencies and verify requirements synchronization.
- Add clean-environment package install, wheel, and container tests.
- Generate SBOM and review dependency/container provenance.
- Document supported Python/provider/framework/backend versions and known platform limits.
- Add changelog, version policy, schema compatibility policy, security reporting path, and release notes.
- Add CI examples for advisory and enforcing scan thresholds.
- Keep live provider tests optional and clearly report which provider capabilities were contract-tested versus live-tested.

First-time user UX:
- Conduct a clean-room walkthrough from README only: install, help, scan fixture, inspect finding, create plan, dry-run apply, verify, doctor.
- Record and fix unclear setup, surprising prompts, noisy output, missing next actions, and undocumented artifacts.
- Ensure no credentials are requested for the first useful result.
- Ensure public docs say alpha, unsupported, and not verified where appropriate.

Release decision:
- Do not declare alpha merely because all phases have code.
- Compare benchmark results to thresholds agreed in docs/product/scope.md.
- If quality is inadequate, publish an internal benchmark report and mark the release blocked with specific metric gaps.
- Do not add TypeScript or another framework as a last-minute substitute for quality.

Run the complete suite and reproducible builds. Update all public documentation with measured claims. Append the completion record with benchmark version, results, release artifacts, known limitations, and the explicit alpha go/no-go decision.
```

## Phase Completion Record

Not started.
