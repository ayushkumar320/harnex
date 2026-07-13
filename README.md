# AutoHarness

AutoHarness audits AI agent repositories for reliability and safety gaps, then generates reviewable fixes for patterns it can verify.

Most agent projects eventually need the same supporting infrastructure: bounded retries, structured logs, side-effect controls, sandboxing, and regression checks. AutoHarness makes those gaps visible before it tries to change anything.

> **Project status:** design and bootstrap stage. The CLI shell and development environment exist; scanner and generation behavior are delivered phase by phase under [`docs/build/`](docs/build/README.md).

## Product Principle

**Audit first, generate second.**

A scan is useful even when AutoHarness cannot safely modify a repository. Unknown behavior is reported with evidence instead of being hidden behind confident-looking generated code.

```text
Target repository
    -> static scan
    -> evidence-backed findings
    -> reviewed plan for supported patterns
    -> constrained generation
    -> isolated verification
```

## Intended Workflow

```bash
harness scan .
harness plan .
harness apply .
harness verify .
harness doctor .
```

| Command | Responsibility |
| --- | --- |
| `scan` | Read-only analysis with source evidence and confidence |
| `plan` | Proposed policies, files, dependencies, and unresolved decisions |
| `apply` | Apply an approved, reviewable diff |
| `verify` | Run deterministic checks in an isolated environment |
| `doctor` | Report provider, sandbox, runtime, and configuration drift |

Example scan summary:

```text
Entrypoint: agent/main.py:run_agent        confidence: 96%
Model calls: 3 detected
External side effects: 2 detected
Unsafe retry boundary: agent/email.py:42
Missing structured logging: 3 call sites
Sandbox coverage: incomplete
Generated fixes available: 4
Manual decisions required: 2
```

## Initial Scope

The first credible release is intentionally narrow:

- Python 3.12 repositories
- CLI and single-function entry points
- Direct OpenAI-compatible, Groq, and Hugging Face model calls
- One LangGraph entry-point adapter after direct providers are stable
- Shell and filesystem tool detection
- JSONL reporting and logs
- Provider-call retries before external side effects
- One enforceable Docker sandbox backend
- Deterministic smoke tests and fault injection

AutoHarness will report unsupported patterns instead of silently generating code for them.

## Free-First Model Strategy

The scanner and policy engine are deterministic and work without a model. Model assistance is optional and used only for ambiguous summaries, documentation-grounded policy suggestions, draft adapters, and draft semantic evals.

The first provider adapters target:

- [Hugging Face Inference](https://huggingface.co/docs/huggingface_hub/en/guides/inference)
- [Groq's OpenAI-compatible API](https://console.groq.com/docs/openai)
- Configurable OpenAI-compatible local or hosted endpoints

Free tiers, quotas, and available models change. AutoHarness therefore discovers provider capability at runtime and never assumes that a particular free model is permanently available.

## Development Setup

Install [uv](https://docs.astral.sh/uv/) and run:

```bash
uv venv
uv pip install -r requirements-dev.txt
uv pip install --no-deps --no-build-isolation -e .
uv run harness --help
```

Copy `.env.example` to `.env` only when testing model-assisted behavior. A read-only scan must not require provider credentials.

## Docker

Build and inspect the CLI bootstrap:

```bash
docker build -t autoharness:dev .
docker run --rm autoharness:dev --help
```

Or use Compose:

```bash
docker compose run --rm autoharness --help
```

The application image is not the sandbox backend. The sandbox backend uses a separate, restricted execution contract introduced in the sandbox phase.

## Documentation

- [Documentation index](docs/README.md)
- [Product vision](docs/product/vision.md)
- [User experience](docs/product/user-experience.md)
- [Scope and success metrics](docs/product/scope.md)
- [Architecture overview](docs/architecture/overview.md)
- [Model-provider strategy](docs/architecture/model-providers.md)
- [Security model](docs/architecture/security.md)
- [Development setup](docs/development/setup.md)
- [Phase-by-phase build plan](docs/build/README.md)
- [Agent contribution contract](AGENTS.md)

## Safety Position

AutoHarness is not proof that an agent is production-safe. Static analysis can miss dynamic behavior, model output is untrusted, retries can duplicate side effects, and a policy file is not a sandbox. Findings always carry evidence, confidence, and a support tier: `verified`, `detected`, `unknown`, or `unsafe`.

## License

No license has been selected yet. Add one before accepting external contributions or distributing packages.
