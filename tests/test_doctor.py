import json
from pathlib import Path

from typer.testing import CliRunner

from autoharness.cli import app

runner = CliRunner()


def test_doctor_reports_missing_credentials_without_provider_calls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    config = tmp_path / "autoharness.yaml"
    config.write_text(
        """
model_assistance:
  enabled: true
  data_policy: remote_allowed
  route:
    - id: groq_fast
      provider: groq
      model: llama
      locality: remote
web_evidence:
  enabled: true
  max_credits_per_command: 2
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["doctor", "--format", "json", "--config", str(config)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["model_assistance"]["route"][0]["missing"] == ["GROQ_API_KEY"]
    assert payload["web_evidence"]["missing"] == ["TAVILY_API_KEY"]


def test_doctor_default_is_deterministic_fallback() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Model assistance: disabled" in result.output
    assert "structural" not in result.output.lower()
