"""Stable application errors and terminal rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.console import Console


@dataclass(frozen=True)
class ErrorContext:
    field: str
    source: str
    expected: str
    next_action: str


class AutoHarnessError(Exception):
    """Base class for user-facing AutoHarness failures."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        context: ErrorContext | None = None,
        exit_code: int = 2,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context
        self.exit_code = exit_code
        self.details = details or {}

    def to_dict(self, *, verbose: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "error": {
                "code": self.code,
                "message": self.message,
            },
        }
        if self.context is not None:
            payload["error"]["field"] = self.context.field
            payload["error"]["source"] = self.context.source
            payload["error"]["expected"] = self.context.expected
            payload["error"]["next_action"] = self.context.next_action
        if verbose and self.details:
            payload["error"]["details"] = self.details
        return payload


class ConfigurationError(AutoHarnessError):
    """Raised when configuration cannot be loaded or validated."""


def render_error(console: Console, error: AutoHarnessError, *, verbose: bool = False) -> None:
    """Render a concise, deterministic error without exposing a traceback."""

    console.print(f"[bold red]{error.code}[/bold red] {error.message}")
    if error.context is not None:
        console.print(f"Field: {error.context.field}")
        console.print(f"Source: {error.context.source}")
        console.print(f"Expected: {error.context.expected}")
        console.print(f"Next: {error.context.next_action}")
    if verbose and error.details:
        console.print("Details:")
        for key in sorted(error.details):
            console.print(f"  {key}: {error.details[key]}")
