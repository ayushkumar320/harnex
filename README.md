# AgentHarness

AgentHarness is the reliability layer an agent needs before it ships: a bounded, logged,
failure-classified wrapper around your provider client, plus an auditor that finds the code that
still needs one.

```python
from openai import OpenAI

from agentharness import wrap

client = wrap(OpenAI())
```

That is the whole adoption cost. `client` keeps the SDK's own API — every attribute and method
passes straight through — but provider calls now carry a request timeout, a bounded retry budget
with backoff, normalized failure classification, and a redacted JSONL event per attempt. No
timeouts to plumb, no retry loop to hand-roll, no code generation.

Run `harness` to find the calls that are not wrapped yet. The auditor never edits your source;
everything it writes lives in a `.agentharness/` directory.

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

It is the thing you run **before** you ship an agent, and in CI so it stays fixed. The auditor
names the gap; `wrap` closes it in one line.

## The Harness

`wrap(client)` returns a proxy that guards only the calls it recognizes as provider calls — the
same method-chain table the static scanner uses, so `harness scan` and `wrap` always agree on what
counts. Everything else on the client is untouched.

```python
from agentharness import wrap

client = wrap(
    OpenAI(),
    timeout=30,             # request timeout, injected only if the callee accepts one
    max_attempts=3,         # hard attempt ceiling
    budget_seconds=90,      # wall-clock ceiling across all attempts
    log_path=".agentharness/runtime.jsonl",   # None to disable
)
```

What it does on a failure:

- classifies the provider exception into a normalized kind — `timeout_before_response`,
  `rate_limited`, `provider_unavailable`, `authentication_failed`, `invalid_request`, and the rest;
- retries only the kinds worth retrying, with exponential backoff and any `Retry-After` the
  provider sent. An auth failure or a malformed request fails on the first attempt, because
  retrying it is just a slower error;
- stops at whichever ceiling comes first, the attempt count or the elapsed budget, then raises
  `GuardedCallFailed` with the original provider exception as its `__cause__`;
- writes one redacted JSONL event per attempt, so a failure has evidence instead of a guess.

For a provider reached through a helper of your own, the decorator form does the same thing:

```python
from agentharness import guard


@guard(timeout=30, max_attempts=3)
def ask(prompt: str) -> str:
    ...
```

A wrapped client satisfies `AH-R101`: audit the repository again and the finding is gone.

### Tools

A provider call is safe to retry. A tool that sends an email is not. `tool` makes you say which,
once, and then enforces it:

```python
from agentharness import tool


@tool(side_effect="read_only")
def search(query: str) -> list[str]:
    ...


@tool(side_effect="idempotent", idempotency_key=lambda path, data: path)
def write_file(path: str, data: str) -> None:
    ...


@tool(side_effect="non_idempotent")
def send_email(to: str, body: str) -> None:
    ...
```

- **read_only** and **idempotent** tools are retried on a transient failure. An idempotent tool
  must supply an `idempotency_key`; once a key has committed in this process, a repeat call
  returns the recorded result instead of running again. That is the "the retry wrote the file
  twice" bug, closed.
- **non_idempotent** tools are never retried. If one fails, whether it committed is genuinely
  unknowable from the outside, so the call raises `CommitStatusUnknown` and says so, rather than
  handing you a silent duplicate or a silent loss.
- **unknown** is the default, and behaves like non_idempotent. An undeclared side effect is not
  safe to retry, so the default is the safe one.

Set `AGENTHARNESS_DRY_RUN=1` and every mutating tool raises `DryRunBlocked` and records the
intent it would have performed, while read-only tools still run. Useful for a first run against
production data.

A declared tool satisfies `AH-S101`.

## What It Finds

| Rule | Severity | What it detects |
| --- | --- | --- |
| `AH-R101` | high | A model-provider call with no detected reliability instrumentation |
| `AH-R102` | medium | A broad `except Exception` that can hide provider or tool failures |
| `AH-R103` | high | A `while True` retry loop whose handler never exits, so it can spin forever |
| `AH-S101` | high | A shell, process, or filesystem write outside a declared `@tool` |
| `AH-S201` | medium | A file containing a credential-shaped value, excluded from analysis |
| `AH-U101` | low | Dynamic import or lookup that static analysis cannot resolve |

Every finding carries evidence: the file, the line, the symbol that triggered it, and a confidence
score. Nothing is inferred from a model.

`AH-R101` recognizes OpenAI, Anthropic, Bedrock, Gemini, Groq, Mistral, Cohere, LiteLLM, Ollama,
and Hugging Face call shapes, and stays quiet when the call already has a timeout, a retry budget,
or a retry decorator in scope. It detects that a control is present, not that it is correct: a
`timeout=99999` silences the rule.

## Install

Requires Python 3.12, 3.13, or 3.14. No API key, no configuration, no network access.

```bash
uv tool install agentgap   # or: pipx install agentgap
```

The package is `agentgap`; the command it installs is `harness`.


A Node toolchain can use the npm wrapper instead. It still needs Python 3.12, 3.13, or 3.14 on `PATH`, and
creates a private virtual environment for the matching wheel.

```bash
npm install -g agentgap
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
