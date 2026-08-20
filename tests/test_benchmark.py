import json
from pathlib import Path

from typer.testing import CliRunner

from agentharness.benchmark import DEFAULT_CORPUS, run_benchmark
from agentharness.cli import app

runner = CliRunner()

CORPUS_CASES = len(json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))["cases"])


def test_alpha_benchmark_runs_labeled_corpus() -> None:
    report = run_benchmark(DEFAULT_CORPUS)

    assert report.metrics.cases == CORPUS_CASES
    assert report.metrics.held_out_cases >= 3
    assert report.metrics.count_precision >= 0.9
    assert report.metrics.count_recall >= 0.9
    assert report.metrics.finding_recall >= 0.9
    assert all(case.status == "passed" for case in report.cases)


def test_benchmark_cli_outputs_machine_readable_report(tmp_path: Path) -> None:
    output = tmp_path / "benchmark.json"

    result = runner.invoke(
        app,
        ["benchmark", "--format", "json", "--output", str(output)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert payload == artifact
    assert payload["artifact_type"] == "benchmark_report"
    assert payload["metrics"]["cases"] == CORPUS_CASES
    assert payload["alpha_decision"] == "go"
