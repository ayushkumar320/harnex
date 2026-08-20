"""Phase 8 alpha benchmark runner."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.table import Table

from agentharness.errors import AgentHarnessError, ErrorContext
from agentharness.scan import scan_repository

BENCHMARK_SCHEMA_VERSION = "1.0"
DEFAULT_CORPUS = Path("docs/benchmark/alpha-corpus.json")


class BenchmarkExpected(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_call_candidates: int
    side_effect_candidates: int
    unknown_dynamic_patterns: int
    parse_failures: int
    finding_rules: list[str] = Field(default_factory=list)


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    path: str
    held_out: bool
    expected: BenchmarkExpected


class BenchmarkCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["benchmark_corpus"] = "benchmark_corpus"
    cases: list[BenchmarkCase]


class BenchmarkCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    path: str
    held_out: bool
    status: Literal["passed", "failed"]
    scan_status: str
    expected: BenchmarkExpected
    actual: BenchmarkExpected
    scan_time_ms: int
    failures: list[str] = Field(default_factory=list)


class BenchmarkMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: int
    held_out_cases: int
    count_precision: float
    count_recall: float
    finding_precision: float
    finding_recall: float
    parse_failure_accuracy: float
    total_scan_time_ms: int


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    artifact_type: Literal["benchmark_report"] = "benchmark_report"
    corpus_path: str
    methodology: str
    metrics: BenchmarkMetrics
    cases: list[BenchmarkCaseResult]
    alpha_decision: Literal["go", "blocked"]
    release_notes: list[str]
    next_action: str


def run_benchmark(corpus_path: Path = DEFAULT_CORPUS) -> BenchmarkReport:
    corpus = _load_corpus(corpus_path)
    results: list[BenchmarkCaseResult] = []
    root = corpus_path.resolve().parents[2] if corpus_path.is_absolute() else Path.cwd()
    for case in corpus.cases:
        results.append(_run_case(case, root=root))
    metrics = _metrics(results)
    decision = _alpha_decision(metrics, results)
    return BenchmarkReport(
        corpus_path=str(corpus_path),
        methodology=(
            "Static scans over labeled Python fixture repositories; no provider calls, "
            "network access, target imports, or generated semantic scoring."
        ),
        metrics=metrics,
        cases=results,
        alpha_decision=decision,
        release_notes=_release_notes(decision),
        next_action=(
            "Publish alpha support claims with these measured limits."
            if decision == "go"
            else "Resolve blocked benchmark cases before public alpha."
        ),
    )


def canonical_benchmark_json(report: BenchmarkReport) -> str:
    payload = report.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_benchmark_report(path: Path, report: BenchmarkReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_benchmark_json(report) + "\n", encoding="utf-8")


def render_benchmark_summary(
    console: Console,
    report: BenchmarkReport,
    *,
    artifact_path: Path,
) -> None:
    console.print("AgentHarness benchmark uses labeled fixtures and no live providers.")
    console.print(f"Corpus: {report.corpus_path}")
    console.print(f"Alpha decision: {report.alpha_decision}")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Cases", str(report.metrics.cases))
    table.add_row("Held-out cases", str(report.metrics.held_out_cases))
    table.add_row("Count precision", f"{report.metrics.count_precision:.2f}")
    table.add_row("Count recall", f"{report.metrics.count_recall:.2f}")
    table.add_row("Finding precision", f"{report.metrics.finding_precision:.2f}")
    table.add_row("Finding recall", f"{report.metrics.finding_recall:.2f}")
    table.add_row("Parse failure accuracy", f"{report.metrics.parse_failure_accuracy:.2f}")
    console.print(table)
    for case in report.cases:
        console.print(f"- {case.id}: {case.status} ({case.scan_time_ms} ms)")
    console.print(f"Detailed JSON: {artifact_path}")
    console.print(f"Next: {report.next_action}")


def _load_corpus(path: Path) -> BenchmarkCorpus:
    try:
        return BenchmarkCorpus.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AgentHarnessError(
            code="AH-B001",
            message="Benchmark corpus could not be read.",
            context=ErrorContext(
                field="corpus",
                source="argument",
                expected="Readable benchmark corpus JSON.",
                next_action="Pass docs/benchmark/alpha-corpus.json or another compatible corpus.",
            ),
            exit_code=3,
        ) from exc


def _run_case(case: BenchmarkCase, *, root: Path) -> BenchmarkCaseResult:
    case_root = root / case.path
    started = time.monotonic()
    report = scan_repository(case_root)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    actual = BenchmarkExpected(
        model_call_candidates=report.summary.model_call_candidates,
        side_effect_candidates=report.summary.side_effect_candidates,
        unknown_dynamic_patterns=report.summary.unknown_dynamic_patterns,
        parse_failures=report.summary.parse_failures,
        finding_rules=[finding.rule_id for finding in report.findings if not finding.suppressed],
    )
    failures = _case_failures(case.expected, actual)
    return BenchmarkCaseResult(
        id=case.id,
        path=case.path,
        held_out=case.held_out,
        status="passed" if not failures else "failed",
        scan_status=report.summary.status,
        expected=case.expected,
        actual=actual,
        scan_time_ms=elapsed_ms,
        failures=failures,
    )


def _case_failures(expected: BenchmarkExpected, actual: BenchmarkExpected) -> list[str]:
    failures: list[str] = []
    for field in [
        "model_call_candidates",
        "side_effect_candidates",
        "unknown_dynamic_patterns",
        "parse_failures",
    ]:
        if getattr(expected, field) != getattr(actual, field):
            failures.append(
                f"{field}: expected {getattr(expected, field)}, got {getattr(actual, field)}"
            )
    if Counter(expected.finding_rules) != Counter(actual.finding_rules):
        failures.append(
            f"finding_rules: expected {expected.finding_rules}, got {actual.finding_rules}"
        )
    return failures


def _metrics(results: list[BenchmarkCaseResult]) -> BenchmarkMetrics:
    expected_counts = 0
    actual_counts = 0
    matching_counts = 0
    expected_findings: Counter[str] = Counter()
    actual_findings: Counter[str] = Counter()
    matching_findings = 0
    parse_matches = 0
    total_scan_time = 0
    for result in results:
        total_scan_time += result.scan_time_ms
        count_fields = [
            "model_call_candidates",
            "side_effect_candidates",
            "unknown_dynamic_patterns",
        ]
        for field in count_fields:
            expected = int(getattr(result.expected, field))
            actual = int(getattr(result.actual, field))
            expected_counts += expected
            actual_counts += actual
            matching_counts += min(expected, actual)
        expected_rule_counts = Counter(result.expected.finding_rules)
        actual_rule_counts = Counter(result.actual.finding_rules)
        expected_findings.update(expected_rule_counts)
        actual_findings.update(actual_rule_counts)
        matching_findings += sum((expected_rule_counts & actual_rule_counts).values())
        if result.expected.parse_failures == result.actual.parse_failures:
            parse_matches += 1
    return BenchmarkMetrics(
        cases=len(results),
        held_out_cases=sum(1 for result in results if result.held_out),
        count_precision=_ratio(matching_counts, actual_counts),
        count_recall=_ratio(matching_counts, expected_counts),
        finding_precision=_ratio(matching_findings, sum(actual_findings.values())),
        finding_recall=_ratio(matching_findings, sum(expected_findings.values())),
        parse_failure_accuracy=_ratio(parse_matches, len(results)),
        total_scan_time_ms=total_scan_time,
    )


def _alpha_decision(
    metrics: BenchmarkMetrics,
    results: list[BenchmarkCaseResult],
) -> Literal["go", "blocked"]:
    if any(result.status == "failed" for result in results):
        return "blocked"
    if metrics.cases < 10 or metrics.held_out_cases < 3:
        return "blocked"
    if min(metrics.count_precision, metrics.count_recall, metrics.finding_recall) < 0.9:
        return "blocked"
    if metrics.finding_precision < 0.85 or metrics.parse_failure_accuracy < 0.9:
        return "blocked"
    return "go"


def _release_notes(decision: Literal["go", "blocked"]) -> list[str]:
    notes = [
        "Python 3.12 static scan is benchmarked without importing target modules.",
        "Generation and verification claims remain limited to direct-provider fixtures.",
        "Live provider behavior is contract-tested with fakes unless explicitly approved.",
        "Docker sandbox support depends on a local Docker daemon and sandbox image.",
    ]
    if decision == "blocked":
        notes.append("Public alpha is blocked until benchmark failures are resolved.")
    else:
        notes.append("Public alpha may proceed with the documented narrow support matrix.")
    return notes


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 4)
