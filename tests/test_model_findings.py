import json
from pathlib import Path

import pytest

from agentharness.model_findings import (
    ModelFindingCandidate,
    synthesize_model_findings,
    validate_model_finding_candidates,
)
from agentharness.providers import (
    DataPolicy,
    FakeModelProvider,
    ModelResponse,
    ProviderCapabilities,
    ProviderKind,
    ProviderLocality,
    RouteEntry,
    RouterConfig,
)
from agentharness.retrieval_models import EvidenceBundle, RetrievedEvidence
from agentharness.scan import scan_repository
from agentharness.scan_models import StructuralFact


def test_model_finding_validator_accepts_catalog_rule_with_existing_evidence() -> None:
    fact = StructuralFact(
        kind="model_call_candidate",
        path="agent.py",
        detector_id="py.model_call",
        evidence_hash="fact:1",
        confidence_basis="Known direct provider call symbol.",
        line=4,
        symbol="client.chat.completions.create",
    )
    candidate = _candidate(evidence_ids=["fact:1"])

    result = validate_model_finding_candidates(
        [candidate],
        facts=[fact],
        bundle=EvidenceBundle(structural_fact_ids=["fact:1"]),
    )

    assert result.rejected == []
    assert len(result.accepted) == 1
    assert result.accepted[0].rule_id == "AH-R101"
    assert result.accepted[0].support == "detected"
    assert result.accepted[0].detector_version == "phase3.model_findings.v1"


def test_model_finding_validator_rejects_missing_evidence_id() -> None:
    result = validate_model_finding_candidates(
        [_candidate(evidence_ids=["missing:1"])],
        facts=[],
        bundle=EvidenceBundle(structural_fact_ids=["fact:1"]),
    )

    assert result.accepted == []
    assert result.rejected[0].field == "evidence_ids"
    assert "missing:1" in result.rejected[0].message


def test_model_finding_validator_rejects_unsupported_rule_and_claimed_support() -> None:
    invalid_rule = _candidate(rule_id="AH-NEW", evidence_ids=["fact:1"])
    claimed_support = _candidate(support="supported", evidence_ids=["fact:1"])

    result = validate_model_finding_candidates(
        [invalid_rule, claimed_support],
        facts=[],
        bundle=EvidenceBundle(structural_fact_ids=["fact:1"]),
    )

    assert [issue.field for issue in result.rejected] == ["rule_id", "support"]


def test_model_finding_validator_rejects_retrieved_evidence_path_escape() -> None:
    bundle = EvidenceBundle(
        local_evidence=[
            RetrievedEvidence(
                id="local:escape",
                source="local_documentation",
                path="../README.md",
                start_line=1,
                end_line=1,
                content_hash="sha256:abc",
                text="untrusted docs",
                score=1,
            )
        ]
    )

    result = validate_model_finding_candidates(
        [_candidate(evidence_ids=["local:escape"])],
        facts=[],
        bundle=bundle,
    )

    assert result.accepted == []
    assert result.rejected[0].field == "evidence.path"


@pytest.mark.asyncio
async def test_model_finding_synthesis_uses_router_and_accepts_valid_json(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / "agent.py",
        """
from openai import OpenAI

def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])
""",
    )
    report = scan_repository(repo)
    fact_id = next(
        fact.evidence_hash for fact in report.facts if fact.kind == "model_call_candidate"
    )
    content = json.dumps({"findings": [_candidate(evidence_ids=[fact_id]).model_dump(mode="json")]})
    provider = FakeModelProvider(
        ProviderCapabilities(structured_json=True),
        [ModelResponse(content=content, finish_reason="stop", latency_ms=1)],
    )
    config = RouterConfig(
        enabled=True,
        data_policy=DataPolicy.LOCAL_ONLY,
        route=[
            RouteEntry(
                id="local_json",
                provider=ProviderKind.OPENAI_COMPATIBLE,
                model="local",
                locality=ProviderLocality.LOCAL,
            )
        ],
        max_attempts_per_provider=1,
        max_total_attempts=1,
    )

    result = await synthesize_model_findings(
        report,
        router_config=config,
        providers={"local_json": provider},
    )

    assert result.status == "complete"
    assert provider.calls == 1
    assert len(result.findings) == 1
    assert result.rejected == []


@pytest.mark.asyncio
async def test_model_finding_synthesis_rejects_malformed_model_output(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "agent.py", "def run():\n    return None\n")
    provider = FakeModelProvider(
        ProviderCapabilities(structured_json=True),
        [
            ModelResponse(
                content='{"findings": [{"rule_id": "AH-R101"}]}',
                finish_reason="stop",
                latency_ms=1,
            )
        ],
    )
    config = RouterConfig(
        enabled=True,
        data_policy=DataPolicy.LOCAL_ONLY,
        route=[
            RouteEntry(
                id="local_json",
                provider=ProviderKind.OPENAI_COMPATIBLE,
                model="local",
                locality=ProviderLocality.LOCAL,
            )
        ],
    )

    result = await synthesize_model_findings(
        scan_repository(repo),
        router_config=config,
        providers={"local_json": provider},
    )

    assert result.status == "rejected_malformed_model_output"
    assert result.findings == []
    assert result.rejected[0].field == "response"


def _candidate(
    *,
    rule_id: str = "AH-R101",
    severity: str = "high",
    support: str = "detected",
    generation: str = "review_required",
    evidence_ids: list[str],
) -> ModelFindingCandidate:
    return ModelFindingCandidate(
        rule_id=rule_id,
        title="Model call lacks reliability controls",
        description="The model call has no detected routing or response validation.",
        impact="Provider failures may be hard to classify.",
        severity=severity,
        support=support,
        confidence_factors=["model_evidence_synthesis"],
        generation=generation,
        evidence_ids=evidence_ids,
        remediation="Route the call through a bounded provider adapter.",
        next_action="Review the cited model call before planning instrumentation.",
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
