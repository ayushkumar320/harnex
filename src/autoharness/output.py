"""Output primitives shared by CLI commands."""

from __future__ import annotations

import json
import os
from enum import StrEnum
from typing import Any

from rich.console import Console


class OutputFormat(StrEnum):
    HUMAN = "human"
    JSON = "json"


class ColorMode(StrEnum):
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


def make_console(*, color: ColorMode, quiet: bool = False, stderr: bool = False) -> Console:
    no_color = color is ColorMode.NEVER or "NO_COLOR" in os.environ
    force_terminal = True if color is ColorMode.ALWAYS and not no_color else None
    return Console(no_color=no_color, force_terminal=force_terminal, quiet=quiet, stderr=stderr)


def print_json(console: Console, payload: dict[str, Any]) -> None:
    console.print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
