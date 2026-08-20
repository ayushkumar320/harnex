# Bootstrap: Testing AgentHarness

A plain-language walkthrough for trying AgentHarness on a real repository. Every command below is
copy-paste ready. No API key is needed for any of it.

If a command surprises you, the rule to remember is: AgentHarness only ever writes inside a
`.agentharness/` folder in the repository you point it at. It never edits your source files.

## 1. What you need

- Python 3.12 or 3.13 on your `PATH`
- This repository checked out
- Docker (optional, only for one sandbox check)

## 2. Install the CLI

From this checkout:

```bash
uv tool install --force .
harness --version
```

`pipx install --force .` works the same way. If you would rather not install anything, prefix every
`harness` command below with `uv run --project /path/to/harnex`, like this:

```bash
uv run --project /path/to/harnex harness --version
```

## 3. Check your setup

```bash
harness doctor
```

This reports which model providers, web-evidence settings, and sandbox capabilities are configured.
Nothing is sent anywhere. Missing pieces are expected: the tests below do not need them.

## 4. Pick a repository to test on

AgentHarness looks for direct model-provider calls in Python: the `openai` SDK, Groq, or Hugging
Face. A repository without those will scan cleanly and report that it found nothing it supports,
which is a valid result, not an error.

If you want a repository that is known to produce findings, use the fixture shipped here:

```bash
harness audit tests/fixtures/repositories/basic_agent
```

For everything below, replace the path with your own repository.

## 5. The safe first look

```bash
cd ~/your-agent-repo
harness audit .
```

`audit` reads your code and writes nothing to your source files. It runs two stages, scan and plan,
and prints one line per stage with its status and where the result was saved. It ends with one
recommended next command.

Look at the details:

```bash
cat .agentharness/scan.json | jq '.findings[] | {id, rule_id, severity, evidence}'
cat .agentharness/plan.json | jq '.actions'
```

Nothing is applied at this point. `plan.json` is a proposal you can read and reject.

## 6. The CI gate

```bash
harness check . --fail-on high
echo "exit code: $?"
```

`check` is the non-interactive version for continuous integration. It exits `1` when your repository
has active findings at the severity you named or worse, and `0` when it does not. Try `--fail-on
low` to see it fail, and `--fail-on critical` to see it pass.

Use it in CI like this:

```yaml
- run: harness check . --fail-on high
```

## 7. The guided repair

This is the only command that writes files. Take a backup or commit your work first.

```bash
harness improve .
```

It asks you two separate questions:

1. **Approve the plan?** This is you agreeing that the proposed actions are reasonable.
2. **Apply these staged files?** This is you agreeing to the exact files it just showed you.

Answering `n` to either one stops immediately, writes no file, and exits with code `4`. Answering
`y` to both writes the generated files, then runs verification.

To run it without prompts, for example in a script:

```bash
harness improve . --yes
```

To skip the verification stage at the end:

```bash
harness improve . --yes --skip-verify
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

## 8. Reading the workflow record

Every workflow command writes one record of what happened:

```bash
cat .agentharness/workflow.json | jq
```

It lists each stage, whether it completed, was skipped, was declined, or failed, how long it took,
which artifact it produced, and one recommended next action. The human output you saw on screen and
this file are the same information.

## 9. Undo everything

```bash
rm -rf .agentharness
```

That removes all artifacts and all generated files, because everything AgentHarness writes lives
there. If you plan to keep using it on a repository, add `.agentharness/` to that repository's
`.gitignore`.

## 10. The step-by-step commands

`audit`, `check`, and `improve` are shortcuts. If you want to see each stage separately, or drive
AgentHarness from a script, the underlying commands are still there:

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

## 11. Machine-readable output

Every command takes `--format json` and prints the same artifact it saved:

```bash
harness audit . --format json
harness check . --fail-on high --format json
```

## 12. About the sandbox check

`harness verify .` runs a set of checks in a throwaway copy of your repository. One of them tries to
prove that AgentHarness can run code with the network denied and the source mounted read-only. That
check needs Docker.

Without Docker it is reported as `not_exercised`, meaning it was never tested. This is not a
failure, and `verify` will not exit non-zero because of it. To actually exercise it:

```bash
docker build -f Dockerfile.sandbox -t agentharness-sandbox .
harness verify .
```

## 13. Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Finished normally |
| `1` | Findings reached the `--fail-on` severity |
| `3` | The scan could not complete on this repository |
| `4` | You declined an approval, or the input was not approved or not fresh |
| `5` | A verification check failed |

## Where to go next

- [README](README.md) for what AgentHarness is and what it deliberately does not do
- [docs/development/v1-test.md](docs/development/v1-test.md) for the fuller validation checklist
- [docs/product/support-matrix.md](docs/product/support-matrix.md) for exactly what is supported
