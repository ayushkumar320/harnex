import subprocess
from pathlib import Path

from agentharness import tool


@tool(side_effect="non_idempotent")
def run_command(cmd):
    return subprocess.run(cmd, shell=True)


@tool(side_effect="idempotent", idempotency_key=lambda path, data: path)
def save(path, data):
    Path(path).write_text(data, encoding="utf-8")
