# Architecture Overview

## System Shape

```text
Repository snapshot
    -> deterministic inventory
    -> language and adapter detectors
    -> structural facts and evidence
    -> local documentation retrieval
    -> optional Tavily external evidence
    -> LLM evidence synthesis and candidate findings
    -> deterministic evidence and policy validation
    -> normalized findings
    -> audit report
    -> optional validated plan
    -> templates and constrained adapters
    -> staged diff
    -> isolated verification
```

The read-only audit is always the primary artifact. Generation is a downstream consumer of supported findings.

## Component Boundaries

### Repository view

Creates a normalized, read-only view of included files. It applies ignore rules, binary and size limits, secret exclusions, path normalization, and content hashes. Downstream scanners do not access arbitrary host paths.

### Scanner

Uses Python `ast` for fast structural facts and LibCST where source-preserving location or transformation information is required. It does not import target modules.

Scanner output is factual:

```json
{
  "kind": "call_site",
  "file": "agent/main.py",
  "line": 42,
  "symbol": "client.chat.completions.create",
  "adapter_candidates": ["openai_compatible"],
  "evidence_hash": "sha256:..."
}
```

### Adapter registry

Adapters interpret facts for a declared compatibility range. Core adapter roles are:

- `EntrypointAdapter`
- `ProviderAdapter`
- `ToolAdapter`
- `FrameworkAdapter`
- `SandboxBackend`
- `ExporterAdapter`

An adapter declares versions, capabilities, confidence rules, fixtures, and conformance tests. Provider SDK objects never cross the adapter boundary.

### Local documentation retrieval

Documentation is optional context, not authority. The MVP starts with lexical and fuzzy retrieval over README files, agent instructions, docs, public docstrings, examples, and test descriptions. Every retrieved chunk includes path, heading or symbol, line range, and content hash.

Repository prose is delimited as untrusted evidence. It cannot alter system policy, enable network access, request secrets, or create a finding without deterministic support.

### External evidence

An `ExternalEvidenceProvider` supplies current public documentation and troubleshooting context. The first implementation uses Tavily Search and Extract with official-domain allowlists, explicit credit budgets, provenance, and content-addressed caching.

External evidence is optional per command and never receives private source code by default. It is passed to the LLM as untrusted, cited context. See [External Evidence Architecture](external-evidence.md).

### LLM reasoning core

The LLM synthesizes structural facts, local documentation, and optional external evidence into candidate findings, explanations, plans, and repository-specific generation proposals. It is the core interpretation layer rather than a cosmetic summarizer.

Deterministic validators bind every claim to evidence, enforce support tiers and permissions, reject unsupported actions, constrain output paths, and validate persistent schemas. The LLM can reason broadly but cannot grant itself authority.

### Finding engine

The finding engine validates LLM-proposed findings against structural facts, adapter interpretation, local documentation, and optional external evidence before producing normalized findings:

```json
{
  "schema_version": "1.0",
  "id": "AH-R201",
  "title": "Unsafe retry after an unknown side effect",
  "severity": "high",
  "support": "detected",
  "confidence": 0.91,
  "generation": "blocked",
  "evidence": [],
  "remediation": []
}
```

Finding IDs and meanings are versioned public contracts.

### Reporter

Produces human terminal output and canonical JSON from the same model. JSON is the source of truth. Human summaries prioritize risk, unknown coverage, and next actions.

### Planner

Consumes findings and proposes a versioned `HarnessPlan`. It never writes files. Every action cites findings and declares:

- Target and adapter
- Required permission
- Dependencies
- Side-effect classification
- Generated files
- Verification checks
- Confidence and approval status

The LLM creates the plan from the validated evidence bundle. Deterministic validation controls whether each action is legal, supported, current, and within approved permissions.

### Generator

Uses tested templates for stable infrastructure and LLM generation for repository-specific adapters, wiring, explanations, and semantic drafts. All generated content is staged, source-attributed where applicable, schema-checked, path-constrained, and reviewed before application.

Generation happens in staging. Paths are constrained under approved roots. Each generated file records generator version, plan hash, template version, and base content hash.

### Verifier

Executes only in a disposable worktree or sandbox. Deterministic checks use fakes, fixture credentials, and denied-by-default network. Results distinguish passed, failed, not exercised, and requires-live-approval.

## Core Schemas

Persisted schemas include:

- `RepositoryInventory`
- `StructuralFact`
- `RetrievedEvidence`
- `ExternalEvidence`
- `EvidenceBundle`
- `Finding`
- `AuditReport`
- `HarnessPlan`
- `GeneratedFileManifest`
- `VerificationReport`
- `RuntimeEvent`

All include a schema version. Changes require compatibility tests and migration decisions.

## Lifecycle and Idempotency

`scan` hashes the included repository view and configuration. `plan` records the source scan hash. `apply` rejects stale plans. Reapplication performs a three-way comparison between the previous generated base, current user file, and new generated result.

The same repository snapshot, configuration, adapter versions, and templates must produce the same deterministic artifacts.

## Runtime Logging

Generated runtime logs use versioned JSON Lines with events such as:

- `run_started`
- `model_call_started` and `model_call_finished`
- `tool_call_started` and `tool_call_finished`
- `retry_scheduled`
- `sandbox_block`
- `run_finished`

Raw prompts and outputs are off by default. Redacted summaries, hashes, sizes, latency, provider, model, token usage, attempt number, and normalized status are preferred.

## Extension Strategy

Add support by implementing a typed adapter plus fixtures and conformance tests. Do not add provider or framework conditionals to core orchestration.

An adapter moves to `verified` only after:

- Declared versions are tested
- Positive and negative detection fixtures pass
- Unknown versions fail closed
- Generated output passes deterministic verification
- Capability claims match observed enforcement

## Related Documents

- [Security model](security.md)
- [Model providers](model-providers.md)
- [External evidence](external-evidence.md)
- [Product scope](../product/scope.md)
- [Build plan](../build/README.md)
