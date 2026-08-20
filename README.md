# AgentHarness

AgentHarness is a read-only auditor for AI agent repositories. It finds the reliability and safety
gaps that agent projects share — unbounded provider retries, unguarded side effects, swallowed
exceptions, leaked secrets — and reports them with file, line, and symbol evidence.

It never edits your source. Everything it writes lives in a `.agentharness/` directory.

> **Project status:** public-alpha candidate. The current implementation supports a narrow Python
> 3.12 static-audit workflow, constrained direct-provider generation, runtime reliability fixtures,
> Docker-backed sandbox smoke verification, deterministic `harness verify`, and a labeled alpha
> benchmark corpus. Unsupported behavior is reported rather than silently transformed.

## The Problem

An agent that works in a demo fails in production for boring reasons. The provider times out and
the retry loop never stops. A tool writes a file, the call is retried, and the file is written
twice. A broad `except Exception` swallows a rate-limit error and the agent silently returns
nothing. An API key ends up in a log line.

None of this is exotic. Every agent project rediscovers the same list, usually after an incident.
AgentHarness is the checklist, run against your actual code instead of your memory.

It is the thing you run **before** you ship an agent, and in CI so it stays fixed.

## What It Finds

| Rule | Severity | What it detects |
| --- | --- | --- |
| `AH-R101` | high | A model-provider call with no detected reliability instrumentation |
| `AH-R102` | medium | A broad `except Exception` that can hide provider or tool failures |
| `AH-S101` | high | A shell, process, or filesystem write with no enforceable boundary |
| `AH-S201` | medium | A file containing a credential-shaped value, excluded from analysis |
| `AH-U101` | low | Dynamic import or lookup that static analysis cannot resolve |

Every finding carries evidence: the file, the line, the symbol that triggered it, and a confidence
score. Nothing is inferred from a model.

## Install

Requires Python 3.12 or 3.13. No API key, no configuration, no network access.

```bash
uv tool install agentharness   # or: pipx install agentharness
```

A Node toolchain can use the npm wrapper instead. It still needs Python 3.12 or 3.13 on `PATH`, and
creates a private virtual environment for the matching wheel.

```bash
npm install -g agentharness
```

## Demo

### 1. Audit

Run it with no arguments inside any repository. This reads your code and writes nothing to it.

```console
$ cd ~/my-agent
$ harness

Workflow: audit
Status: completed
  scan: completed (0 ms) - status=complete
    artifact: .agentharness/scan.json
  plan: completed (0 ms) - status=review_required
    artifact: .agentharness/plan.json
Next action: Review the plan, then run harness improve to stage approved changes.
Workflow artifact: .agentharness/workflow.json
```

### 2. Read the findings

`harness report` renders the scan as Markdown, grouped by severity.

```console
$ harness report
Wrote 16 finding(s) to .agentharness/findings.md
```

```markdown
# AgentHarness findings

Findings: 16 active 3 high, 1 medium, 12 low

## High (3)

### Tool side effect has no enforceable boundary

`AH-S101` · confidence 0.86

Locations:

- `src/storage.py:56` — `path.write_text`

**What it is:** A shell, process, or filesystem write side effect was detected.

**Why it matters:** Retries or verification could mutate external state without an enforcement boundary.

**What to change:** Classify the side effect and run future verification in an enforced sandbox.
```

That file is written to be handed to a coding agent:

```bash
claude "Read .agentharness/findings.md. For each finding, open the file at that line and tell me whether it is a real problem or intentional."
```

Triage before you fix. These are static matches — some flagged sites are deliberate.

### 3. Generate scaffolding

For `AH-R101` findings, AgentHarness can generate a starting point: a bounded runner, a JSONL
logger, a config module, and a smoke test.

```console
$ harness improve

Status: review_required
  Actions                 1
  Blocked findings        0
- plan-action-6743699966 Generate bounded provider runtime scaffolding for detected model call

Approve 1 planned action(s)? [y/N]: y

Status: staged
  Files staged          4

Apply these staged files to the repository? [y/N]: y
```

It asks twice — once for the plan, once for the exact files. Declining either writes nothing and
exits `4`. What lands:

```
.agentharness/generated/agentharness_config.py
.agentharness/generated/agentharness_jsonl_logger.py
.agentharness/generated/agentharness_runner.py
.agentharness/generated/tests/test_agentharness_smoke.py
```

Your own files are untouched. You wire these in yourself.

### 4. Gate CI

```yaml
- run: harness check . --fail-on high
```

Exits `1` when active findings reach that severity, `0` otherwise.

### 5. Undo

```bash
rm -rf .agentharness
```

Everything AgentHarness writes lives there.

## What It Does Not Do

Being clear about this matters more than the feature list.

- **It does not fix your code.** Generation exists for one rule, `AH-R101`, and it emits new files
  next to your code rather than editing it. Every other finding is reported and stops there.
- **It does not prove your agent is safe.** Static analysis misses dynamic behavior, and a policy
  file is not a sandbox.
- **It does not detect failures, it detects patterns.** A flagged `subprocess.run` may be exactly
  what your program is for. Findings are a review queue, not a work order.
- **It does not call a model.** The default scan is deterministic and offline.

## Product Principle

**Audit first, generate second.**

A scan is useful even when AgentHarness cannot safely modify a repository. Unknown behavior is
reported with evidence instead of being hidden behind confident-looking generated code.

```text
Target repository
    -> static scan
    -> evidence-backed findings
    -> reviewed plan for supported patterns
    -> constrained generation
    -> isolated verification
    -> measured alpha benchmark
```

## Commands

The three you need:

```bash
harness            # read-only audit of the current directory (same as `harness audit .`)
harness report     # render findings as Markdown for review or for a coding agent
harness improve    # audit, stage a diff, ask for approval, apply, then verify
```

Plus `harness check --fail-on high` for CI. Every command takes `--format json`.

Each stage is also a command, for scripting and debugging:

| Command | Responsibility |
| --- | --- |
| `audit` | Read-only scan and plan in one command |
| `report` | Render a scan artifact as a Markdown findings brief |
| `improve` | Approval-gated scan, plan, stage, apply, and verify |
| `check` | Non-interactive severity gate for CI |
| `scan` | Read-only analysis with source evidence and confidence |
| `plan` | Proposed policies, files, dependencies, and unresolved decisions |
| `approve` | Record explicit approval for supported generation actions in a plan |
| `apply` | Preview or apply an approved, reviewable generated diff |
| `verify` | Run deterministic checks in a disposable workspace with denied-network sandbox checks |
| `benchmark` | Measure the labeled alpha fixture corpus without live provider calls |
| `doctor` | Report provider, web-evidence, sandbox, and configuration readiness |

`approve` is the safety boundary: a fresh plan is always unapproved, and `apply` refuses to run on
an unapproved plan.

New here? [BOOTSTRAP.md](BOOTSTRAP.md) is a plain-language walkthrough.

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
- [Final-year and product-extension plans](docs/nextplans/README.md)
- [Agent contribution contract](AGENTS.md)

## Safety Position

AgentHarness is not proof that an agent is production-safe. Static analysis can miss dynamic behavior, model output is untrusted, retries can duplicate side effects, and a policy file is not a sandbox. Findings carry evidence, confidence, support tier, and generation state. Verification reports separate `passed`, `failed`, `not_exercised`, and `requires_approval`.

## License

[MIT](LICENSE)
