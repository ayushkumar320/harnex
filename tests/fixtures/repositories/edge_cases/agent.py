import subprocess
from pathlib import Path


def risky_tool() -> None:
    name = "dynamic_name"
    subprocess.run(["echo", "hello"])
    Path("state.txt").write_text("state")
    getattr(Path, name)
