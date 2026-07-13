# Architecture Overview

## System Shape

```text
Repository snapshot
    -> deterministic inventory
    -> language and adapter detectors
    -> structural facts and evidence
    -> optional local documentation retrieval
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

### Documentation retrieval

Documentation is optional context, not authority. The MVP starts with lexical and fuzzy retrieval over README files, agent instructions, docs, public docstrings, examples, and test descriptions. Every retrieved chunk includes path, heading or symbol, line range, and content hash.

Repository prose is delimited as untrusted evidence. It cannot alter system policy, enable network access, request secrets, or create a finding without deterministic support.

### Finding engine

Rules combine structural facts, adapter interpretation, and optional documentation evidence into normalized findings:

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

Model assistance may explain ambiguous evidence, but deterministic validation controls whether an action is legal.

### Generator

Uses tested templates for retry state machines, logging schemas, sandbox adapters, and eval runners. Model-generated content is limited to reviewable drafts such as semantic cases or unsupported adapter suggestions.

Generation happens in staging. Paths are constrained under approved roots. Each generated file records generator version, plan hash, template version, and base content hash.

### Verifier

Executes only in a disposable worktree or sandbox. Deterministic checks use fakes, fixture credentials, and denied-by-default network. Results distinguish passed, failed, not exercised, and requires-live-approval.

## Core Schemas

Persisted schemas include:

- `RepositoryInventory`
- `StructuralFact`
- `RetrievedEvidence`
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
- [Product scope](../product/scope.md)
- [Build plan](../build/README.md)
