# AgentHarness

AgentHarness audits AI agent repositories for reliability and safety gaps, then generates reviewable fixes for patterns it can verify.

Most agent projects eventually need the same supporting infrastructure: bounded retries, structured logs, side-effect controls, sandboxing, and regression checks. AgentHarness makes those gaps visible before it tries to change anything.

> **Project status:** public-alpha candidate. The current implementation supports a narrow Python 3.12 static-audit workflow, constrained direct-provider generation, runtime reliability fixtures, Docker-backed sandbox smoke verification, deterministic `harness verify`, and a labeled alpha benchmark corpus. Unsupported behavior is reported rather than silently transformed.

## Product Principle

**Audit first, generate second.**

A scan is useful even when AgentHarness cannot safely modify a repository. Unknown behavior is reported with evidence instead of being hidden behind confident-looking generated code.

```text
Target repository
    -> static scan
    -> evidence-backed findings
    -> reviewed plan for supported patterns
    -> constrained generation
    -> isolated verification
    -> measured alpha benchmark
```

## Intended Workflow

Start with the two orchestrating commands. They compose the low-level commands below and need no
credentials.

```bash
harness audit .     # read-only: scan and plan in one command
harness improve .   # audit, stage a diff, ask for approval, apply, then verify
harness check .     # non-interactive CI gate, exits 1 on findings at or above --fail-on
```

`improve` asks twice: once to approve the plan, once to apply the exact staged files. Declining
either leaves the repository untouched and exits `4`. Every stage is recorded in
`.agentharness/workflow.json`.

The low-level commands remain available for automation and debugging:

```bash
harness scan .
harness plan .
harness approve .agentharness/plan.json
harness apply .agentharness/plan.json --dry-run
harness apply .agentharness/plan.json --yes
harness verify .
harness benchmark
harness doctor
```

| Command | Responsibility |
| --- | --- |
| `audit` | Read-only scan and plan in one command |
| `improve` | Approval-gated scan, plan, stage, apply, and verify |
| `check` | Non-interactive severity gate for CI |
| `scan` | Read-only analysis with source evidence and confidence |
| `plan` | Proposed policies, files, dependencies, and unresolved decisions |
| `approve` | Record explicit approval for supported generation actions in a plan |
| `apply` | Preview or apply an approved, reviewable generated diff |
| `verify` | Run deterministic checks in a disposable workspace with denied-network sandbox checks |
| `benchmark` | Measure the labeled alpha fixture corpus without live provider calls |
| `doctor` | Report provider, web-evidence, sandbox, and configuration readiness |

## Initial Scope

The alpha support claim is intentionally narrow:

- Python 3.12 repositories
- Static scan without importing target modules
- CLI and single-function entry-point evidence
- Direct OpenAI-compatible, Groq, and Hugging Face model-call patterns
- Shell/process and filesystem-write side-effect detection
- JSON scan, plan, apply, verify, and benchmark artifacts
- Deterministic JSONL runtime logging templates
- Provider-call retries before external side effects
- One Docker sandbox backend using a separate target-execution image
- Fixture-driven verification and benchmark reporting

AgentHarness will report unsupported patterns instead of silently generating code for them.

## Install

AgentHarness is a Python 3.12/3.13 CLI. Install it with `pipx` (or `uv tool`):

```bash
pipx install agentharness
harness --version
```

A Node-based toolchain can use the npm wrapper instead. It still requires Python 3.12 or 3.13 on
`PATH`; it creates a private virtual environment and installs the matching wheel into it.

```bash
npm install -g agentharness
harness --version
```

## Development Setup

Install [uv](https://docs.astral.sh/uv/) and run:

```bash
uv sync --all-extras --locked
uv run harness --help
```

Run the read-only scanner:

```bash
uv run harness scan . --output .agentharness/scan.json
uv run harness scan . --format json --output .agentharness/scan.json
uv run harness scan . --output .agentharness/scan.json --fail-on high
```

`scan` parses Python files as data. It does not import target modules, run setup hooks, execute tests, or call model providers.
When opt-in web evidence is enabled, its cache is stored outside the target repository under the
AgentHarness user cache directory. Set `AGENTHARNESS_CACHE_DIR` to choose a different cache root.

Inspect provider, web-evidence, and sandbox configuration without sending repository evidence:

```bash
uv run harness doctor
uv run harness doctor --format json
```

Build the target-execution sandbox image before sandbox-backed verification:

```bash
docker build -f Dockerfile.sandbox -t agentharness-sandbox:dev .
uv run harness verify . --output .agentharness/verify.json
```

Run the alpha benchmark:

```bash
uv run harness benchmark --output docs/benchmark/alpha-results.json
```

Copy `.env.example` to `.env` only when testing model-assisted behavior. A read-only scan and the default benchmark do not require provider credentials.

For packaging and deployment, see the [startup and package release guide](docs/development/startup-and-release.md).

## Docker

Build and inspect the CLI application image:

```bash
docker build -t agentharness:dev .
docker run --rm agentharness:dev --version
```

Build the separate sandbox image:

```bash
docker build -f Dockerfile.sandbox -t agentharness-sandbox:dev .
```

The application image is not the sandbox backend. The sandbox backend uses the separate target-execution image and fails closed when Docker or the image is unavailable.

## Alpha Benchmark

The checked-in alpha corpus lives at [`docs/benchmark/alpha-corpus.json`](docs/benchmark/alpha-corpus.json). It includes 10 fixture repositories, including held-out cases for dynamic lookup, broad retry, prompt injection prose, secret-like documentation, and syntax errors.

The benchmark distinguishes static detection metrics from generation and verification success. It does not run live model providers and does not score semantic correctness.

## Documentation

- [Documentation index](docs/README.md)
- [Product vision](docs/product/vision.md)
- [User experience](docs/product/user-experience.md)
- [Scope and success metrics](docs/product/scope.md)
- [Architecture overview](docs/architecture/overview.md)
- [Model-provider strategy](docs/architecture/model-providers.md)
- [External web evidence](docs/architecture/external-evidence.md)
- [Security model](docs/architecture/security.md)
- [Development setup](docs/development/setup.md)
- [CI usage](docs/development/ci.md)
- [Phase-by-phase build plan](docs/build/README.md)
- [Final-year and product-extension plans](docs/nextplans/README.md)
- [Agent contribution contract](AGENTS.md)

## Safety Position

AgentHarness is not proof that an agent is production-safe. Static analysis can miss dynamic behavior, model output is untrusted, retries can duplicate side effects, and a policy file is not a sandbox. Findings carry evidence, confidence, support tier, and generation state. Verification reports separate `passed`, `failed`, `not_exercised`, and `requires_approval`.

## License

[MIT](LICENSE)
