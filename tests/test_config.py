from pathlib import Path

import pytest

from autoharness.config import ConfigOverrides, load_config
from autoharness.errors import ConfigurationError


def test_defaults_do_not_require_provider_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AUTOHARNESS_OUTPUT_FORMAT",
        "AUTOHARNESS_MODEL_PROVIDER",
        "GROQ_API_KEY",
        "HF_TOKEN",
        "OPENAI_COMPATIBLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    config = load_config()

    assert config.output_format == "human"
    assert config.model_provider == "disabled"


def test_configuration_precedence_flags_env_file_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "autoharness.yaml"
    config_file.write_text(
        """
output_format: human
log_level: warning
telemetry_enabled: true
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTOHARNESS_OUTPUT_FORMAT", "json")

    config = load_config(
        ConfigOverrides(
            config_path=config_file,
            output_format="human",
        )
    )

    assert config.output_format == "human"
    assert config.log_level == "WARNING"
    assert config.telemetry_enabled is True
    assert config.model_provider == "disabled"


def test_invalid_environment_value_names_field_and_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOHARNESS_OUTPUT_FORMAT", "xml")

    with pytest.raises(ConfigurationError) as exc_info:
        load_config()

    error = exc_info.value
    assert error.code == "AH-C001"
    assert error.context is not None
    assert error.context.field == "output_format"
    assert error.context.source == "environment"
    assert "human" in error.context.expected


def test_missing_config_file_is_user_facing_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        load_config(ConfigOverrides(config_path=tmp_path / "missing.yaml"))

    assert exc_info.value.code == "AH-C002"


def test_phase_two_route_config_loads_from_file(tmp_path: Path) -> None:
    config_file = tmp_path / "autoharness.yaml"
    config_file.write_text(
        """
model_assistance:
  enabled: true
  data_policy: local_only
  route:
    - id: local
      provider: openai_compatible
      model: local-model
      locality: local
      base_url: http://127.0.0.1:11434/v1
  deadlines:
    attempt_seconds: 1
    operation_seconds: 2
web_evidence:
  enabled: false
  max_credits_per_command: 1
""",
        encoding="utf-8",
    )

    config = load_config(ConfigOverrides(config_path=config_file))

    assert config.model_assistance.enabled is True
    assert config.model_assistance.data_policy == "local_only"
    assert config.model_assistance.route[0].id == "local"
    assert config.model_assistance.attempt_seconds == 1
    assert config.web_evidence.max_credits_per_command == 1


def test_legacy_provider_env_builds_route_without_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOHARNESS_MODEL_PROVIDER", "openai_compatible")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("AUTOHARNESS_OPENAI_COMPATIBLE_MODEL", "local-demo")

    config = load_config()

    assert config.model_assistance.enabled is True
    assert config.model_assistance.data_policy == "local_only"
    assert config.model_assistance.route[0].id == "openai_compatible_env"
    assert config.model_assistance.route[0].model == "local-demo"


def test_route_config_rejects_duplicate_ids(tmp_path: Path) -> None:
    config_file = tmp_path / "autoharness.yaml"
    config_file.write_text(
        """
model_assistance:
  enabled: true
  data_policy: remote_allowed
  route:
    - id: duplicate
      provider: groq
      model: llama
      locality: remote
    - id: duplicate
      provider: huggingface
      model: hf
      locality: remote
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_config(ConfigOverrides(config_path=config_file))
