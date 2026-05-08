#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..");
const args = process.argv.slice(2);

function pythonCandidates() {
  const configuredPython = process.env.RUNPROOF_PYTHON;
  if (configuredPython) {
    return [[configuredPython, []]];
  }
  if (process.platform === "win32") {
    return [["py", ["-3"]], ["python", []], ["python3", []]];
  }
  return [["python3", []], ["python", []]];
}

function runPython(command, prefixArgs) {
  const env = { ...process.env };
  env.PYTHONPATH = env.PYTHONPATH
    ? `${packageRoot}${path.delimiter}${env.PYTHONPATH}`
    : packageRoot;
  return spawnSync(command, [...prefixArgs, "-m", "runproof", ...args], {
    cwd: process.cwd(),
    env,
    stdio: "inherit",
  });
}

for (const [command, prefixArgs] of pythonCandidates()) {
  const result = runPython(command, prefixArgs);
  if (!result.error) {
    process.exit(result.status === null ? 1 : result.status);
  }
  if (result.error.code !== "ENOENT") {
    console.error(`runproof failed to launch Python via ${command}: ${result.error.message}`);
    process.exit(1);
  }
}

console.error("runproof requires Python 3.11+ on PATH. Set RUNPROOF_PYTHON to a Python executable if needed.");
process.exit(1);
