"use strict";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const IS_WINDOWS = process.platform === "win32";
const MIN = [3, 12];
const MAX_EXCLUSIVE = [3, 15];
const VENV_DIR = path.join(__dirname, "..", ".venv");

// Candidate interpreters, most specific first, so a system default outside the
// supported range does not shadow a usable interpreter that is also installed.
const CANDIDATES = IS_WINDOWS
  ? ["py -3.14", "py -3.13", "py -3.12", "python3", "python"]
  : ["python3.14", "python3.13", "python3.12", "python3", "python"];

function versionOf(command) {
  const parts = command.split(" ");
  try {
    const out = execFileSync(parts[0], [...parts.slice(1), "-c", "import sys;print('%d.%d' % sys.version_info[:2])"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return out.trim().split(".").map(Number);
  } catch {
    return null;
  }
}

function supported(version) {
  if (!version || version.length < 2 || version.some(Number.isNaN)) return false;
  const [major, minor] = version;
  if (major !== MIN[0]) return false;
  return minor >= MIN[1] && minor < MAX_EXCLUSIVE[1];
}

function findPython() {
  for (const command of CANDIDATES) {
    if (supported(versionOf(command))) return command.split(" ");
  }
  return null;
}

function venvBin(name) {
  return IS_WINDOWS
    ? path.join(VENV_DIR, "Scripts", `${name}.exe`)
    : path.join(VENV_DIR, "bin", name);
}

function venvReady() {
  return fs.existsSync(venvBin("harness"));
}

module.exports = { IS_WINDOWS, VENV_DIR, findPython, venvBin, venvReady };
