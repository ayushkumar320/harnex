#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");

const { venvBin, venvReady } = require("../lib/python.js");

if (!venvReady()) {
  console.error(
    "agentharness: the bundled Python environment is missing.\n" +
      "Reinstall the package (npm install -g agentharness), or run the install step:\n" +
      "  node " + require.resolve("../install.js"),
  );
  process.exit(1);
}

const result = spawnSync(venvBin("harness"), process.argv.slice(2), { stdio: "inherit" });

if (result.error) {
  console.error(`agentharness: ${result.error.message}`);
  process.exit(1);
}
// A signalled child has a null status; report it the way a shell would.
process.exit(result.status === null ? 128 : result.status);
