# AutoHarness Documentation

This directory is the source of truth for product intent, architecture, development, and delivery.

## Start Here

| Reader | Recommended path |
| --- | --- |
| New contributor | [Vision](product/vision.md) -> [User experience](product/user-experience.md) -> [Architecture](architecture/overview.md) -> [Setup](development/setup.md) |
| Product reviewer | [Vision](product/vision.md) -> [Scope](product/scope.md) -> [Build plan](build/README.md) |
| Security reviewer | [Security model](architecture/security.md) -> [Architecture](architecture/overview.md) -> [Sandbox phase](build/06-sandbox-enforcement.md) |
| Implementation agent | [AGENTS.md](../AGENTS.md) -> active phase document -> linked architecture references |
| Model-provider contributor | [Provider strategy](architecture/model-providers.md) -> [Provider phase](build/02-provider-and-retrieval.md) |
| Web-evidence contributor | [External evidence](architecture/external-evidence.md) -> [Provider and retrieval phase](build/02-provider-and-retrieval.md) |

## Product

- [Product vision](product/vision.md): problem, differentiation, principles, and long-term direction
- [User experience](product/user-experience.md): workflows, emotions, CLI behavior, and failure communication
- [Scope and metrics](product/scope.md): support tiers, MVP boundaries, non-goals, and measurable success

## Architecture

- [Architecture overview](architecture/overview.md): components, contracts, data flow, and lifecycle
- [Model providers](architecture/model-providers.md): free-first provider abstraction and fallback behavior
- [External evidence](architecture/external-evidence.md): Tavily search, documentation snapshots, provenance, privacy, and credit controls
- [Security model](architecture/security.md): trust boundaries, retries, sandboxing, redaction, and verification

## Development

- [Local and Docker setup](development/setup.md): UV, requirements, environment variables, quality checks, and containers

## Build

- [Build-plan index](build/README.md): phase order, dependencies, milestones, and delivery rules
- Every phase has a self-contained Codex prompt, acceptance gates, product outcome, and UX target.

## Documentation Rules

- Keep the root README concise and public-facing.
- Put reasons and user outcomes in `product/`.
- Put system contracts and invariants in `architecture/`.
- Put executable delivery instructions in `build/`.
- Update [`AGENTS.md`](../AGENTS.md) when a rule applies to every phase.
- Do not copy changing provider model names or free-tier quotas into multiple files.
