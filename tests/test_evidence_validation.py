from agentharness.evidence_validation import CitedModelOutput, validate_citations
from agentharness.retrieval_models import EvidenceBundle, RetrievedEvidence


def test_validate_citations_rejects_missing_evidence_ids() -> None:
    bundle = EvidenceBundle(
        structural_fact_ids=["fact:1"],
        local_evidence=[
            RetrievedEvidence(
                id="local:1",
                source="local_documentation",
                path="README.md",
                start_line=1,
                end_line=2,
                content_hash="sha256:abc",
                text="docs",
                score=1,
            )
        ],
    )
    output = CitedModelOutput(text="claim", evidence_ids=["local:1", "missing:1"])

    result = validate_citations(output, bundle)

    assert result.valid is False
    assert result.missing_evidence_ids == ["missing:1"]


def test_validate_citations_accepts_structural_and_local_ids() -> None:
    bundle = EvidenceBundle(structural_fact_ids=["fact:1"])
    output = CitedModelOutput(text="claim", evidence_ids=["fact:1"])

    assert validate_citations(output, bundle).valid is True
