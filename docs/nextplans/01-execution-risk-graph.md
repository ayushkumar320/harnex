# Next Phase N1: Execution-Risk Graph and HTML Report

## Product Outcome

AutoHarness turns validated structural facts and findings into an evidence-linked execution
graph and accessible HTML report, helping developers understand where models, retries,
tools, data, and side effects interact.

## User Problem

Linear findings can describe one defect but make cross-component risk difficult to see. A
developer needs to understand which entry point reaches a side effect, where retries wrap
that path, what data reaches a provider, and which portions are unknown.

## Prerequisites

- Build Phase 1 structural facts and repository evidence
- Build Phase 3 normalized findings and support tiers
- Stable relative source paths and evidence IDs

## Scope

- Versioned `ExecutionRiskGraph` with typed nodes and edges.
- Node kinds: entry point, model call, provider route, tool, side effect, retry boundary,
  datastore/filesystem boundary, policy boundary, and unknown dynamic region.
- Edge kinds: calls, data_may_flow_to, retries, falls_back_to, may_commit, guarded_by, and
  unresolved.
- Evidence, detector/adapter version, confidence factors, and support tier on every inferred
  relationship.
- Deterministic graph construction; LLMs may propose labels or candidate edges, but
  deterministic evidence validation decides inclusion.
- Accessible self-contained HTML report with summary, filters, finding details, source links,
  and text/table alternative to the graph.
- Explainable `ReliabilityProfile` dimensions for provider resilience, side-effect safety,
  failure observability, privacy, tool containment, and verification coverage. Each dimension
  reports satisfied, failed, unknown, and not-measured rules; there is no opaque overall
  safety score.
- Bounded layout for large repositories with component grouping and truncation notices.

## Non-Claims

The graph is a supported static approximation, not a complete runtime call graph, taint proof,
or guarantee that an edge executes. Unknown dynamic registration must appear as unknown, not
as an absent path.

## Deliverables

- Graph schema and deterministic graph builder
- JSON export and canonical ordering
- HTML renderer with no remote assets or scripts
- Reliability-profile schema and deterministic dimension calculation
- Finding-to-node and evidence-to-source navigation
- Graph fixtures for direct calls, retries, provider fallback, side effects, and unknown
  dynamic registration
- Accessibility and hostile-content tests

## Acceptance Gates

- Every node and edge is backed by valid evidence or explicitly labeled unknown/inferred.
- Repeated input produces byte-stable graph JSON and stable semantic HTML.
- HTML contains no repository secrets, remote resources, executable repository content, or
  unescaped hostile labels.
- Findings and graph counts agree with the canonical audit artifact.
- Every profile dimension links to its contributing rules, findings, evidence, unknowns, and
  not-measured capabilities.
- A non-visual table communicates the same relationships.
- A repository above graph limits receives grouping and truncation metadata, not a frozen UI.

## Out of Scope

- Executing the repository to discover runtime paths
- Claiming complete data-flow or call-graph precision
- Building a hosted dashboard
- Arbitrary interactive code execution in the report

## Detailed Codex Prompt

```text
You are the lead engineer implementing AutoHarness Next Phase N1: execution-risk graph and HTML report.

Act as:
1. A senior static-analysis engineer designing explainable graph semantics from incomplete evidence.
2. An information-visualization engineer making complex agent flows understandable without hiding uncertainty.
3. A security engineer treating paths, labels, snippets, and report content as hostile data.

Before editing:
- Read AGENTS.md, architecture overview, security model, Build Phases 1 and 3, this phase, and prerequisite completion records.
- Inspect the actual StructuralFact, Evidence, Finding, and provider-route schemas.
- Define node and edge semantics with examples and non-claims before writing the renderer.

Implement the canonical graph:
- Create versioned ExecutionRiskGraph, RiskNode, RiskEdge, GraphEvidenceRef, and GraphCoverage schemas.
- Build nodes and edges deterministically from validated structural facts, findings, adapters, and provider route configuration.
- Require evidence references and named confidence factors for inferred edges.
- Represent unknown dynamic regions and disconnected facts visibly.
- Use canonical IDs derived from stable fact or evidence IDs, never display labels.

Implement reporting:
- Export canonical JSON first; derive HTML and terminal summaries from it.
- Define ReliabilityProfile and ProfileDimension from deterministic rule outcomes. Report
  numerator, denominator, unknown, and not-measured coverage without a single overall score.
- Produce a self-contained accessible HTML report with no CDN, tracking, or network dependency.
- Add filters by severity, support, node type, and finding while preserving a text/table alternative.
- Escape all content, neutralize terminal/browser control characters, bound snippets, and prevent path traversal in source links.
- Group large graphs by module or component and record every omitted detail.

Testing and evaluation:
- Golden-test direct provider calls, fallback, unsafe retry around a side effect, safe retry, unknown registration, parse failure, and disconnected facts.
- Test malicious filenames, HTML/script payloads, giant labels, cycles, duplicate facts, and missing evidence.
- Measure graph construction time and report size by fact count.
- Conduct a small comprehension test: compare time to locate a seeded risky path using text-only findings versus the graph report.

Run all standard and prerequisite gates. Append the completion record with supported graph semantics, measured limits, accessibility results, and known blind spots.
```

## Phase Completion Record

Not started.
