import pytest

from autoharness.external_evidence import (
    EvidenceSearchRequest,
    FakeExternalEvidenceProvider,
    estimate_search_cost,
    external_evidence,
    validate_official_domain,
    validate_query_privacy,
)


def test_external_query_privacy_rejects_secret_like_material() -> None:
    with pytest.raises(ValueError):
        validate_query_privacy("openai OPENAI_API_KEY=sk-secret")


def test_external_budget_and_domain_policy() -> None:
    request = EvidenceSearchRequest(
        query="openai chat completions create",
        include_domains=["platform.openai.com"],
        credits_remaining=0,
    )

    assert estimate_search_cost(request).allowed is False
    assert validate_official_domain("https://platform.openai.com/docs", ["platform.openai.com"])
    with pytest.raises(ValueError):
        validate_official_domain("https://example.com/docs", ["platform.openai.com"])


@pytest.mark.asyncio
async def test_fake_external_provider_filters_to_official_domains() -> None:
    evidence = external_evidence(
        url="https://platform.openai.com/docs",
        title="OpenAI Docs",
        text="Official docs",
        query="openai docs",
        allowed_domains=["platform.openai.com"],
    )
    provider = FakeExternalEvidenceProvider([evidence])
    results = await provider.search(
        EvidenceSearchRequest(
            query="openai docs",
            include_domains=["platform.openai.com"],
            credits_remaining=1,
        )
    )

    assert provider.calls == 1
    assert results == [evidence]
