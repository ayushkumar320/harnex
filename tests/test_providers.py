import pytest

from autoharness.providers import (
    DataPolicy,
    FailureKind,
    FakeModelProvider,
    ModelRequest,
    ModelResponse,
    ModelRouter,
    ProviderCapabilities,
    ProviderFailure,
    ProviderKind,
    ProviderLocality,
    RouteEntry,
    RouterConfig,
    build_manifest,
)


@pytest.mark.asyncio
async def test_router_fails_over_from_groq_timeout_to_huggingface_success() -> None:
    manifest = build_manifest(data_policy=DataPolicy.REMOTE_ALLOWED, local_evidence_ids=["local:1"])
    request = ModelRequest(
        messages=[{"role": "user", "content": "hi"}],
        model="unused",
        evidence_manifest=manifest,
    )
    config = RouterConfig(
        enabled=True,
        data_policy=DataPolicy.REMOTE_ALLOWED,
        route=[
            RouteEntry(
                id="groq_fast",
                provider=ProviderKind.GROQ,
                model="g",
                locality=ProviderLocality.REMOTE,
            ),
            RouteEntry(
                id="hf_backup",
                provider=ProviderKind.HUGGINGFACE,
                model="h",
                locality=ProviderLocality.REMOTE,
            ),
        ],
        max_attempts_per_provider=1,
        max_total_attempts=2,
    )
    providers = {
        "groq_fast": FakeModelProvider(
            ProviderCapabilities(),
            [ProviderFailure(kind=FailureKind.TIMEOUT_BEFORE_RESPONSE, message="timeout")],
        ),
        "hf_backup": FakeModelProvider(
            ProviderCapabilities(),
            [ModelResponse(content="ok", finish_reason="stop", latency_ms=1)],
        ),
    }

    result = await ModelRouter(config, providers).complete(request)

    assert result.status == "complete"
    assert [attempt.route_id for attempt in result.attempts] == ["groq_fast", "hf_backup"]
    assert result.response is not None
    assert result.response.content == "ok"


@pytest.mark.asyncio
async def test_router_local_only_makes_zero_remote_calls() -> None:
    manifest = build_manifest(data_policy=DataPolicy.LOCAL_ONLY, local_evidence_ids=["local:1"])
    request = ModelRequest(
        messages=[{"role": "user", "content": "hi"}],
        model="unused",
        evidence_manifest=manifest,
    )
    remote_provider = FakeModelProvider(
        ProviderCapabilities(),
        [ModelResponse(content="should not call", finish_reason="stop", latency_ms=1)],
    )
    config = RouterConfig(
        enabled=True,
        data_policy=DataPolicy.LOCAL_ONLY,
        route=[
            RouteEntry(
                id="groq_fast",
                provider=ProviderKind.GROQ,
                model="g",
                locality=ProviderLocality.REMOTE,
            )
        ],
    )

    result = await ModelRouter(config, {"groq_fast": remote_provider}).complete(request)

    assert result.status == "incomplete_model_unavailable"
    assert result.attempts == []
    assert remote_provider.calls == 0


@pytest.mark.asyncio
async def test_router_disabled_returns_structural_only_without_attempts() -> None:
    manifest = build_manifest(data_policy=DataPolicy.DISABLED, local_evidence_ids=[])
    request = ModelRequest(
        messages=[{"role": "user", "content": "hi"}],
        model="unused",
        evidence_manifest=manifest,
    )

    result = await ModelRouter(RouterConfig(), {}).complete(request)

    assert result.status == "incomplete_model_unavailable"
    assert result.incomplete_reason == "model_assistance_disabled"
    assert result.attempts == []
