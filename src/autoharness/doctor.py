"""Repository-free diagnostics for Phase 2 configuration."""

from __future__ import annotations

import os
from typing import Any

from autoharness.config import AppConfig
from autoharness.providers import ProviderKind, ProviderLocality


def doctor_report(config: AppConfig) -> dict[str, Any]:
    route_reports = []
    for entry in config.model_assistance.route:
        missing = _missing_credentials(entry.provider, entry.locality)
        route_reports.append(
            {
                "id": entry.id,
                "provider": entry.provider.value,
                "model": entry.model,
                "locality": entry.locality.value,
                "configured": not missing,
                "missing": missing,
            }
        )
    return {
        "schema_version": "1.0",
        "command": "doctor",
        "status": "ok",
        "model_assistance": {
            "enabled": config.model_assistance.enabled,
            "data_policy": config.model_assistance.data_policy.value,
            "route": route_reports,
            "deterministic_fallback": "structural_inventory",
        },
        "web_evidence": {
            "enabled": config.web_evidence.enabled,
            "provider": config.web_evidence.provider,
            "max_credits_per_command": config.web_evidence.max_credits_per_command,
            "missing": (
                [] if _has_tavily_key() or not config.web_evidence.enabled else ["TAVILY_API_KEY"]
            ),
        },
    }


def _missing_credentials(provider: ProviderKind, locality: ProviderLocality) -> list[str]:
    if locality is ProviderLocality.LOCAL:
        return []
    if provider is ProviderKind.GROQ and not os.environ.get("GROQ_API_KEY"):
        return ["GROQ_API_KEY"]
    if provider is ProviderKind.HUGGINGFACE and not os.environ.get("HF_TOKEN"):
        return ["HF_TOKEN"]
    if provider is ProviderKind.OPENAI_COMPATIBLE and not os.environ.get(
        "OPENAI_COMPATIBLE_API_KEY"
    ):
        return ["OPENAI_COMPATIBLE_API_KEY"]
    return []


def _has_tavily_key() -> bool:
    return bool(os.environ.get("TAVILY_API_KEY"))
