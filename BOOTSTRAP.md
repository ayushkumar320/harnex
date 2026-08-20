# Getting Started with AgentHarness

AgentHarness audits an AI agent repository for missing reliability controls and generates
reviewable code you can adopt. It only ever writes inside a `.agentharness/` folder in the
repository you point it at. It never edits your source files. No API key is needed.

## The three commands

```bash
uv tool install agentgap
```

The package is `agentgap`; the command it installs is `harness`.


`pipx install agentgap` works the same way. To install from a local checkout instead, pass the
path: `uv tool install --force /path/to/harnex`.

Then, from inside your repository:

| Command | What it does | Writes source files? |
| --- | --- | --- |
| `harness` | Read-only audit of the current directory | No |
| `harness improve` | Audit, show the plan, apply it after you approve, verify | Yes, into `.agentharness/generated/` |
| `harness check --fail-on high` | Non-interactive CI gate, exits `1` on findings | No |
| `harness report` | Render the findings as Markdown for a coding agent | No |

That is the whole workflow. Everything below is detail.

## Try it without installing

```bash
uv run --project /path/to/harnex harness
```

To see it produce findings, point it at the fixture shipped in this repository:

```bash
harness audit tests/fixtures/repositories/basic_agent
```

`harness` with no arguments is the same as `harness audit .`.

## What the audit found

```bash
cat .agentharness/scan.json | jq '.findings[] | {id, rule_id, severity, evidence}'
cat .agentharness/plan.json | jq '.actions'
```

`plan.json` is a proposal. Nothing is applied until you approve it.

## The guided repair

```bash
harness improve
```

It asks two separate questions:

1. **Approve the plan?** You agree the proposed actions are reasonable.
2. **Apply these staged files?** You agree to the exact files it just showed you.

Answering `n` to either stops immediately, writes no file, and exits with code `4`.

Non-interactive variants:

```bash
harness improve --yes
harness improve --yes --skip-verify
```

What it writes:

```
.agentharness/generated/agentharness_config.py
.agentharness/generated/agentharness_jsonl_logger.py
.agentharness/generated/agentharness_runner.py
.agentharness/generated/tests/test_agentharness_smoke.py
```

These are reviewable starting points for bounded retries, structured JSONL logging, and a smoke
test. Your own files are untouched.

## The CI gate

```bash
harness check --fail-on high
```

Exits `1` when active findings reach that severity, `0` otherwise. In GitHub Actions:

```yaml
- run: harness check . --fail-on high
```

## Reading the workflow record

Every workflow command writes one record of what happened:

```bash
cat .agentharness/workflow.json | jq
```

It lists each stage, whether it completed, was skipped, declined, or failed, how long it took,
which artifact it produced, and one recommended next action.

## Undo everything

```bash
rm -rf .agentharness
```

Everything AgentHarness writes lives there. If you keep using it on a repository, add
`.agentharness/` to that repository's `.gitignore`.

## Checking your setup

```bash
harness doctor
```

Reports which model providers, web-evidence settings, and sandbox capabilities are configured.
Nothing is sent anywhere. Missing pieces are expected: none of the above needs them.

## What is supported

AgentHarness looks for direct model-provider calls in Python: the `openai` SDK, Groq, or Hugging
Face. A repository without those scans cleanly and reports that it found nothing it supports.
That is a valid result, not an error. See
[docs/product/support-matrix.md](docs/product/support-matrix.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Finished normally |
| `1` | Findings reached the `--fail-on` severity |
| `3` | The scan could not complete on this repository |
| `4` | You declined an approval, or the input was not approved or not fresh |
| `5` | A verification check failed |

---

# Appendix: the scriptable stages

`harness`, `harness improve`, and `harness check` are the front door. Underneath, each stage is a
separate command you can drive from a script or run one at a time:

```bash
harness scan . --output .agentharness/scan.json
harness plan .agentharness/scan.json --output .agentharness/plan.json
harness approve .agentharness/plan.json --yes
harness apply .agentharness/plan.json --dry-run --output .agentharness/apply-preview.json
harness apply .agentharness/plan.json --yes --output .agentharness/apply-preview.json
harness verify .
```

The `approve` step matters: a fresh plan is always unapproved, and `apply` refuses to run on an
unapproved plan. That refusal is the safety boundary, not a bug.

## Machine-readable output

Every command takes `--format json` and prints the same artifact it saved:

```bash
harness audit . --format json
harness check . --fail-on high --format json
```

## The sandbox check

`harness verify .` runs checks in a throwaway copy of your repository. One of them proves
AgentHarness can run code with the network denied and the source mounted read-only. That check
needs Docker.

Without Docker it is reported as `not_exercised`, meaning it was never tested. This is not a
failure, and `verify` will not exit non-zero because of it. To actually exercise it:

```bash
docker build -f Dockerfile.sandbox -t agentharness-sandbox .
harness verify .
```

## Where to go next

- [README](README.md) for what AgentHarness is and what it deliberately does not do
- [docs/development/v1-test.md](docs/development/v1-test.md) for the fuller validation checklist
