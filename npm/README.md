# AgentHarness (npm wrapper)

AgentHarness is a read-only auditor for AI agent repositories. It finds the reliability and safety
gaps that agent projects share — unbounded provider retries, unguarded side effects, swallowed
exceptions, leaked secrets — and reports them with file, line, and symbol evidence.

It never edits your source. Everything it writes lives in a `.agentharness/` directory.

AgentHarness is a Python tool. This package is a thin npm wrapper for teams whose toolchain is
already Node-based: installing it creates a private virtual environment inside the package
directory and installs the matching `agentharness` wheel from PyPI into it. The `harness` command
then forwards every argument and exit code to that interpreter.

## Requirements

- Node.js 18 or newer
- Python 3.12 or 3.13 available on `PATH`

Installation fails with instructions if no supported interpreter is found. Set
`AGENTHARNESS_SKIP_INSTALL=1` to skip the Python install step, for example when vendoring
`node_modules` in an image build that installs the Python package separately.

## Install

```bash
npm install -g agentharness
harness --version
```

If you do not need the Node entry point, install the Python package directly instead:

```bash
uv tool install agentharness   # or: pipx install agentharness
```

## Usage

Run it with no arguments inside any repository. This reads your code and writes nothing to it.

```bash
harness            # read-only audit of the current directory
harness report     # render the findings as Markdown for review or for a coding agent
harness improve    # audit, stage a diff, ask for approval, apply, then verify
```

For CI, `harness check . --fail-on high` exits `1` when an active finding meets the threshold and
`0` otherwise.

## What it finds

| Rule | Severity | What it detects |
| --- | --- | --- |
| `AH-R101` | high | A model-provider call with no detected reliability instrumentation |
| `AH-R102` | medium | A broad `except Exception` that can hide provider or tool failures |
| `AH-S101` | high | A shell, process, or filesystem write with no enforceable boundary |
| `AH-S201` | medium | A file containing a credential-shaped value, excluded from analysis |
| `AH-U101` | low | Dynamic import or lookup that static analysis cannot resolve |

Generation exists for `AH-R101` only, and it writes new scaffolding files rather than editing your
code. Every other finding is reported and stops there. Findings are static pattern matches: treat
them as a review queue, not a work order.

See the [project README](https://github.com/ayushkumar320/harnex) for the full command reference,
supported scope, and safety position.

## License

MIT
