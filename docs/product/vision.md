# Product Vision

## The Problem

AI agent projects often reach a convincing demo before they gain the controls needed for repeated use. Each repository then rebuilds the same supporting behavior:

- Provider error classification and bounded retries
- Side-effect and idempotency controls
- Structured model and tool-call logs
- Shell, filesystem, browser, and network isolation
- Regression checks for prompts, models, and tools
- Failure reports that explain what happened

This infrastructure is easy to omit because it is not the agent's headline feature. When a run fails, the developer may not know whether the provider, model output, tool, policy, or application caused it.

## The Vision

AutoHarness is a reliability auditor first and a constrained generator second.

It inspects an agent repository without executing it, identifies model calls, tool boundaries, entry points, external side effects, and missing reliability controls, and emits findings tied to source evidence. For verified patterns, it can propose a harness and apply a reviewed diff. Unsupported patterns remain useful findings rather than speculative code.

The product principle is:

> **Audit first, generate second.**

## Why This Shape Is Credible

The broad promise "make any agent production-ready" cannot be verified. Static analysis cannot fully resolve reflection, dynamic registration, runtime dependency injection, generated code, or unknown side effects.

The focused promise is defensible:

> Analyze documented Python agent patterns, explain reliability gaps with evidence, and generate tested controls only through verified adapters.

The read-only audit is the initial product. Generation is an optional acceleration layer.

## Product Workflow

```text
scan -> understand findings -> plan -> review -> apply -> verify -> monitor drift
```

1. `harness scan .` analyzes without importing or executing target code.
2. `harness plan .` turns supported findings into a versioned proposal.
3. The developer reviews permissions, assumptions, dependencies, and the diff.
4. `harness apply .` writes only approved files.
5. `harness verify .` exercises deterministic controls in isolation.
6. `harness doctor .` detects missing providers, sandbox capabilities, stale plans, and drift.

## Differentiation

Observability products explain instrumented runs. Sandbox products isolate execution. Agent frameworks provide framework-native execution controls. AutoHarness focuses on the repository-analysis layer that connects these concerns.

It should integrate with, not compete with, established systems:

- Export logs or traces to LangSmith, Langfuse, or OpenTelemetry.
- Use Docker or an isolated remote runtime as an enforcement backend.
- Wrap supported framework entry points without forcing a rewrite.
- Generate starter eval structures while leaving semantic oracle approval to the developer.

## Product Principles

### Evidence over confidence

Every finding includes source location, rule or adapter, confidence, severity, and remediation. The LLM may propose findings, but deterministic evidence binding and policy validation decide whether they become reportable artifacts.

### Unsupported is a valid result

AutoHarness must say what it could not understand. Unknown side effects and unsupported adapters block generation but do not invalidate the audit.

### Reversibility

Scanning is read-only. Plans are inspectable. Generated files include provenance. Reapplication uses a three-way comparison and never silently overwrites user edits.

### LLM reasoning with deterministic guardrails

The LLM is central to interpreting repository intent, combining evidence, producing findings and plans, and generating repository-specific adaptations. AST analysis, evidence binding, schema validation, retry state machines, path enforcement, permission checks, and security assertions remain deterministic so model reasoning cannot silently expand authority.

### Free-first, provider-neutral reasoning

Development should work with no paid model by supporting Groq, Hugging Face, and local or hosted OpenAI-compatible endpoints. A no-model run may produce structural inventory, but full interpretation is explicitly incomplete. Free availability is treated as a runtime condition, not a permanent product assumption.

### Current external evidence

For fast-changing SDKs and providers, Tavily can supply current official documentation, migration notes, and capability evidence to the LLM. Web retrieval is explicit, source-attributed, cached, credit-budgeted, and never treated as policy authority.

### Honest safety

A generated policy is not an enforcement boundary. A passing smoke test is not proof of safety. AutoHarness reports exactly what was tested and what remains unverified.

## Long-Term Direction

If the narrow MVP earns trust, AutoHarness can grow into:

- A CI reliability policy that catches new unbounded calls or unsafe tools
- A community adapter ecosystem with conformance tests
- Baseline-to-current drift reporting
- Framework and language expansion driven by benchmark evidence
- Optional observability exporters and remote sandbox backends
- A corpus of seeded agent reliability failures for evaluation

The durable asset is not generated boilerplate. It is the evidence model, adapter contracts, conformance suite, and benchmark corpus.
