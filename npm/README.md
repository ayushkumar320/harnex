# AgentHarness (npm wrapper)

AgentHarness audits AI agent repositories for reliability and safety gaps, then generates
reviewable fixes for patterns it can verify.

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
pipx install agentharness
```

## Usage

```bash
harness scan .
harness plan .
harness apply . --dry-run
harness verify .
harness doctor
```

`harness scan . --fail-on high` exits with code `1` when a finding meets the threshold, which
makes it usable as a CI gate.

See the [project README](https://github.com/ayushkumar/agentharness) for the full command
reference, supported scope, and safety position.

## License

MIT
