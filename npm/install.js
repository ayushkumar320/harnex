"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const { VENV_DIR, findPython, venvBin } = require("./lib/python.js");

const pkg = require("./package.json");
// Overridable so CI can smoke-test the wrapper against a local wheel before the
// matching version exists on PyPI.
const REQUIREMENT = process.env.AGENTHARNESS_PYTHON_REQUIREMENT || `agentgap==${pkg.pythonVersion}`;

const NO_PYTHON = `
agentgap requires Python >=3.12,<3.14 on PATH, and none was found.

Install Python 3.12 or 3.13, then reinstall this package:
  https://www.python.org/downloads/

The Python package can also be installed directly, without npm:
  pipx install ${REQUIREMENT}
`;

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} exited with ${result.status}`);
  }
}

function main() {
  if (process.env.AGENTHARNESS_SKIP_INSTALL) {
    console.log("agentgap: AGENTHARNESS_SKIP_INSTALL set, skipping Python install.");
    return;
  }

  const python = findPython();
  if (!python) {
    console.error(NO_PYTHON);
    process.exit(1);
  }

  // A venv left over from a previous version would pin the old wheel.
  fs.rmSync(VENV_DIR, { recursive: true, force: true });

  const [exe, ...prefix] = python;
  run(exe, [...prefix, "-m", "venv", VENV_DIR]);
  run(venvBin("python"), ["-m", "pip", "install", "--disable-pip-version-check", "--quiet", "--upgrade", "pip"]);
  run(venvBin("python"), ["-m", "pip", "install", "--disable-pip-version-check", "--quiet", REQUIREMENT]);

  if (!fs.existsSync(venvBin("harness"))) {
    throw new Error(`install completed but ${venvBin("harness")} is missing`);
  }
  console.log(`agentharness: installed ${REQUIREMENT} into ${path.relative(process.cwd(), VENV_DIR)}`);
}

try {
  main();
} catch (error) {
  console.error(`agentharness: install failed: ${error.message}`);
  console.error(`Install the Python package directly instead: pipx install ${REQUIREMENT}`);
  process.exit(1);
}
