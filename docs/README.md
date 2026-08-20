# AgentHarness Documentation

This directory is the source of truth for product intent, architecture, development, and delivery.

## Start Here

| Reader | Recommended path |
| --- | --- |
| New contributor | [Vision](product/vision.md) -> [User experience](product/user-experience.md) -> [Architecture](architecture/overview.md) -> [Setup](development/setup.md) |
| Product reviewer | [Vision](product/vision.md) -> [Scope](product/scope.md) |
| Final-year project reviewer | [Next plans](nextplans/README.md) -> [Benchmark and evaluation](nextplans/06-benchmark-and-final-evaluation.md) |
| Security reviewer | [Security model](architecture/security.md) -> [Architecture](architecture/overview.md) |
| Implementation agent | [AGENTS.md](../AGENTS.md) -> active phase document -> linked architecture references |
| Model-provider contributor | [Provider strategy](architecture/model-providers.md) |
| Web-evidence contributor | [External evidence](architecture/external-evidence.md) |

## Product

- [Product vision](product/vision.md): problem, differentiation, principles, and long-term direction
- [User experience](product/user-experience.md): workflows, emotions, CLI behavior, and failure communication
- [Scope and metrics](product/scope.md): support tiers, MVP boundaries, non-goals, and measurable success
- [Alpha support matrix](product/support-matrix.md): supported versions, backend claims, and known limits

## Architecture

- [Architecture overview](architecture/overview.md): components, contracts, data flow, and lifecycle
- [Model providers](architecture/model-providers.md): free-first provider abstraction and fallback behavior
- [External evidence](architecture/external-evidence.md): Tavily search, documentation snapshots, provenance, privacy, and credit controls
- [Security model](architecture/security.md): trust boundaries, retries, sandboxing, redaction, and verification

## Development

- [Local and Docker setup](development/setup.md): UV, requirements, environment variables, quality checks, and containers
- [V1 test guide](development/v1-test.md): plain-language command walkthrough for testing the current alpha candidate
- [Startup and package release guide](development/startup-and-release.md): local startup, package builds, TestPyPI/PyPI, and container release
- [CI usage](development/ci.md): read-only scan gates, artifact upload examples, and fixture precision snapshot

## Build

- Every phase has a self-contained Codex prompt, acceptance gates, product outcome, and UX target.

## Next Plans

- [Final-year extension roadmap](nextplans/README.md): optional prerequisite-gated plans for
  one-command workflows, execution-risk visualization, policy as code, failure injection,
  repair measurement, CI drift, and reproducible academic evaluation
- Next plans do not replace the active build order and must not be presented as implemented
  before their own acceptance gates and baseline prerequisites pass.

## Documentation Rules

- Keep the root README concise and public-facing.
- Put reasons and user outcomes in `product/`.
- Put system contracts and invariants in `architecture/`.
- Put executable delivery instructions in `build/`.
- Put optional post-baseline and final-year extension plans in `nextplans/`.
- Update [`AGENTS.md`](../AGENTS.md) when a rule applies to every phase.
- Do not copy changing provider model names or free-tier quotas into multiple files.
