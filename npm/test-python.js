"use strict";
// Self-check for the interpreter gate: node npm/test-python.js
const assert = require("node:assert");
const { findPython, venvBin, IS_WINDOWS } = require("./lib/python.js");

// Re-derive `supported` behavior through findPython on a real interpreter: the
// gate must reject anything outside >=3.12,<3.14.
const python = findPython();
if (python) {
  const { execFileSync } = require("node:child_process");
  const [exe, ...prefix] = python;
  const out = execFileSync(exe, [...prefix, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"], {
    encoding: "utf8",
  }).trim();
  const [major, minor] = out.split(".").map(Number);
  assert.strictEqual(major, 3, `selected interpreter is Python ${out}`);
  assert.ok(minor >= 12 && minor < 14, `selected interpreter is Python ${out}, outside >=3.12,<3.14`);
  console.log(`ok: selected Python ${out}`);
} else {
  console.log("ok: no supported interpreter found, wrapper will fail closed");
}

assert.ok(venvBin("harness").endsWith(IS_WINDOWS ? "harness.exe" : "harness"));
console.log("ok: venv binary path");
