"""Configuration loading with explicit source precedence."""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from autoharness.errors import ConfigurationError, ErrorContext
from autoharness.external_evidence import WebEvidenceConfig
from autoharness.output import ColorMode, OutputFormat
from autoharness.providers import (
    DataPolicy,
    ProviderKind,
    ProviderLocality,
    RouteEntry,
    RouterConfig,
)


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ModelProvider(StrEnum):
    DISABLED = "disabled"
    GROQ = "groq"
    HUGGINGFACE = "huggingface"
    OPENAI_COMPATIBLE = "openai_compatible"


class Source(StrEnum):
    DEFAULT = "default"
    CONFIG_FILE = "config file"
    ENVIRONMENT = "environment"
    FLAG = "flag"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    schema_version: Literal["1.0"] = "1.0"
    output_format: OutputFormat = OutputFormat.HUMAN
    color: ColorMode = ColorMode.AUTO
    log_level: LogLevel = LogLevel.INFO
    telemetry_enabled: bool = False
    model_provider: ModelProvider = ModelProvider.DISABLED
    model_assistance: RouterConfig = Field(default_factory=RouterConfig)
    web_evidence: WebEvidenceConfig = Field(default_factory=WebEvidenceConfig)
    config_path: Path | None = None

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.upper()
        return value


class ConfigValue(BaseModel):
    value: Any
    source: Source


class ConfigOverrides(BaseModel):
    output_format: str | None = None
    color: str | None = None
    log_level: str | None = None
    telemetry_enabled: bool | None = None
    model_provider: str | None = None
    config_path: Path | None = None


ENV_MAP = {
    "output_format": "AUTOHARNESS_OUTPUT_FORMAT",
    "color": "AUTOHARNESS_COLOR",
    "log_level": "AUTOHARNESS_LOG_LEVEL",
    "telemetry_enabled": "AUTOHARNESS_TELEMETRY_ENABLED",
    "model_provider": "AUTOHARNESS_MODEL_PROVIDER",
}

DEFAULTS: dict[str, ConfigValue] = {
    "output_format": ConfigValue(value=OutputFormat.HUMAN, source=Source.DEFAULT),
    "color": ConfigValue(value=ColorMode.AUTO, source=Source.DEFAULT),
    "log_level": ConfigValue(value=LogLevel.INFO, source=Source.DEFAULT),
    "telemetry_enabled": ConfigValue(value=False, source=Source.DEFAULT),
    "model_provider": ConfigValue(value=ModelProvider.DISABLED, source=Source.DEFAULT),
    "model_assistance": ConfigValue(value=RouterConfig(), source=Source.DEFAULT),
    "web_evidence": ConfigValue(value=WebEvidenceConfig(), source=Source.DEFAULT),
    "config_path": ConfigValue(value=None, source=Source.DEFAULT),
}


def load_config(overrides: ConfigOverrides | None = None) -> AppConfig:
    overrides = overrides or ConfigOverrides()
    values = DEFAULTS.copy()

    config_path = overrides.config_path or _default_config_path()
    if config_path is not None:
        file_values = _load_config_file(config_path)
        for field, value in file_values.items():
            values[field] = ConfigValue(value=value, source=Source.CONFIG_FILE)
        values["config_path"] = ConfigValue(value=config_path, source=Source.CONFIG_FILE)

    for field, env_name in ENV_MAP.items():
        if env_name in os.environ and os.environ[env_name] != "":
            raw_value = os.environ[env_name]
            values[field] = ConfigValue(
                value=_coerce_env_value(field, raw_value),
                source=Source.ENVIRONMENT,
            )
            if field == "model_provider":
                values["model_assistance"] = ConfigValue(
                    value=_router_from_legacy_provider(raw_value),
                    source=Source.ENVIRONMENT,
                )

    if "AUTOHARNESS_WEB_EVIDENCE_ENABLED" in os.environ:
        web = _mapping_value(values["web_evidence"].value)
        web["enabled"] = _coerce_env_value(
            "web_evidence.enabled",
            os.environ["AUTOHARNESS_WEB_EVIDENCE_ENABLED"],
        )
        values["web_evidence"] = ConfigValue(value=web, source=Source.ENVIRONMENT)
    if "AUTOHARNESS_TAVILY_MAX_CREDITS" in os.environ:
        web = _mapping_value(values["web_evidence"].value)
        web["max_credits_per_command"] = int(os.environ["AUTOHARNESS_TAVILY_MAX_CREDITS"])
        values["web_evidence"] = ConfigValue(value=web, source=Source.ENVIRONMENT)

    for field, value in overrides.model_dump(exclude_none=True).items():
        values[field] = ConfigValue(value=value, source=Source.FLAG)

    raw = {field: item.value for field, item in values.items()}
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"])
        source = values.get(field, ConfigValue(value=None, source=Source.DEFAULT)).source.value
        raise ConfigurationError(
            code="AH-C001",
            message="Invalid configuration.",
            context=ErrorContext(
                field=field,
                source=source,
                expected=_expected_for(field),
                next_action=(
                    "Change the flag, environment variable, or config file value and retry."
                ),
            ),
            details={"validation_error": first["msg"]},
        ) from exc


def _default_config_path() -> Path | None:
    for candidate in (Path("autoharness.yaml"), Path("autoharness.yml")):
        if candidate.exists():
            return candidate
    return None


def _load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(
            code="AH-C002",
            message="Configuration file was not found.",
            context=ErrorContext(
                field="config_path",
                source="flag",
                expected="A readable YAML file path.",
                next_action="Pass an existing file or omit --config.",
            ),
        )
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            code="AH-C003",
            message="Configuration file is not valid YAML.",
            context=ErrorContext(
                field="config_path",
                source="config file",
                expected="Valid YAML with AutoHarness settings.",
                next_action="Fix the YAML syntax and retry.",
            ),
            details={"path": str(path)},
        ) from exc
    if not isinstance(document, Mapping):
        raise ConfigurationError(
            code="AH-C004",
            message="Configuration file must contain a mapping.",
            context=ErrorContext(
                field="config_path",
                source="config file",
                expected="YAML key-value settings.",
                next_action="Replace the file contents with a YAML mapping.",
            ),
        )
    section = document.get("autoharness", document)
    if not isinstance(section, Mapping):
        raise ConfigurationError(
            code="AH-C004",
            message="Configuration section must contain a mapping.",
            context=ErrorContext(
                field="autoharness",
                source="config file",
                expected="YAML key-value settings.",
                next_action="Make the autoharness section a mapping.",
            ),
        )
    return dict(section)


def _coerce_env_value(field: str, value: str) -> Any:
    if field in {"telemetry_enabled", "web_evidence.enabled"}:
        lowered = value.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return value


def _mapping_value(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _router_from_legacy_provider(provider: str) -> RouterConfig:
    normalized = provider.lower()
    if normalized == ModelProvider.DISABLED:
        return RouterConfig()
    if normalized == ModelProvider.GROQ:
        return RouterConfig(
            enabled=True,
            data_policy=DataPolicy.REMOTE_ALLOWED,
            route=[
                RouteEntry(
                    id="groq_env",
                    provider=ProviderKind.GROQ,
                    model=os.environ.get("AUTOHARNESS_GROQ_MODEL", "llama-3.1-8b-instant"),
                    locality=ProviderLocality.REMOTE,
                )
            ],
        )
    if normalized == ModelProvider.HUGGINGFACE:
        model = os.environ.get("AUTOHARNESS_HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
        return RouterConfig(
            enabled=True,
            data_policy=DataPolicy.REMOTE_ALLOWED,
            route=[
                RouteEntry(
                    id="hf_env",
                    provider=ProviderKind.HUGGINGFACE,
                    model=model,
                    locality=ProviderLocality.REMOTE,
                )
            ],
        )
    if normalized == ModelProvider.OPENAI_COMPATIBLE:
        base_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://127.0.0.1:11434/v1")
        return RouterConfig(
            enabled=True,
            data_policy=DataPolicy.LOCAL_ONLY
            if base_url.startswith(("http://127.0.0.1", "http://localhost"))
            else DataPolicy.REMOTE_ALLOWED,
            route=[
                RouteEntry(
                    id="openai_compatible_env",
                    provider=ProviderKind.OPENAI_COMPATIBLE,
                    model=os.environ.get("AUTOHARNESS_OPENAI_COMPATIBLE_MODEL", "local-model"),
                    locality=ProviderLocality.LOCAL
                    if base_url.startswith(("http://127.0.0.1", "http://localhost"))
                    else ProviderLocality.REMOTE,
                    base_url=base_url,
                )
            ],
        )
    return RouterConfig()


def _expected_for(field: str) -> str:
    expected = {
        "output_format": "one of: human, json",
        "color": "one of: auto, always, never",
        "log_level": "one of: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        "telemetry_enabled": "a boolean value",
        "model_provider": "one of: disabled, groq, huggingface, openai_compatible",
        "config_path": "a readable YAML file path",
    }
    return expected.get(field, "a supported AutoHarness setting")
