import pytest

from autoharness.providers import (
    DataPolicy,
    FailureKind,
    FakeModelProvider,
    FileCircuitStore,
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
    assert result.skipped[0].skip_reason == "local_only_policy"
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


@pytest.mark.asyncio
async def test_router_skips_open_circuit_and_uses_next_provider() -> None:
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
                id="local",
                provider=ProviderKind.OPENAI_COMPATIBLE,
                model="l",
                locality=ProviderLocality.LOCAL,
            ),
        ],
    )
    providers = {
        "groq_fast": FakeModelProvider(
            ProviderCapabilities(),
            [ModelResponse(content="no", finish_reason="stop", latency_ms=1)],
        ),
        "local": FakeModelProvider(
            ProviderCapabilities(),
            [ModelResponse(content="ok", finish_reason="stop", latency_ms=1)],
        ),
    }
    router = ModelRouter(config, providers)
    router.open_circuits["groq_fast"] = 9999999999

    result = await router.complete(request)

    assert result.response is not None
    assert result.response.content == "ok"
    assert result.skipped[0].route_id == "groq_fast"
    assert result.skipped[0].skip_reason == "circuit_open"


@pytest.mark.asyncio
async def test_router_allows_optional_json_schema_capability_reduction() -> None:
    manifest = build_manifest(data_policy=DataPolicy.REMOTE_ALLOWED, local_evidence_ids=["local:1"])
    request = ModelRequest(
        messages=[{"role": "user", "content": "json"}],
        model="unused",
        required_capabilities=["chat_completion", "json_schema"],
        schema_enforcement_required=False,
        evidence_manifest=manifest,
    )
    provider = FakeModelProvider(
        ProviderCapabilities(structured_json=True, json_schema=False),
        [ModelResponse(content='{"ok": true}', finish_reason="stop", latency_ms=1)],
    )
    config = RouterConfig(
        enabled=True,
        data_policy=DataPolicy.REMOTE_ALLOWED,
        route=[
            RouteEntry(
                id="jsonish",
                provider=ProviderKind.OPENAI_COMPATIBLE,
                model="j",
                locality=ProviderLocality.REMOTE,
            )
        ],
    )

    result = await ModelRouter(config, {"jsonish": provider}).complete(request)

    assert result.status == "complete"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_router_rejects_required_json_schema_without_capability() -> None:
    manifest = build_manifest(data_policy=DataPolicy.REMOTE_ALLOWED, local_evidence_ids=["local:1"])
    request = ModelRequest(
        messages=[{"role": "user", "content": "json"}],
        model="unused",
        required_capabilities=["chat_completion", "json_schema"],
        schema_enforcement_required=True,
        evidence_manifest=manifest,
    )
    provider = FakeModelProvider(
        ProviderCapabilities(structured_json=True, json_schema=False),
        [ModelResponse(content='{"ok": true}', finish_reason="stop", latency_ms=1)],
    )
    config = RouterConfig(
        enabled=True,
        data_policy=DataPolicy.REMOTE_ALLOWED,
        route=[
            RouteEntry(
                id="jsonish",
                provider=ProviderKind.OPENAI_COMPATIBLE,
                model="j",
                locality=ProviderLocality.REMOTE,
            )
        ],
    )

    result = await ModelRouter(config, {"jsonish": provider}).complete(request)

    assert result.status == "incomplete_model_unavailable"
    assert result.skipped[0].skip_reason == "unsupported_capability:json_schema"
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_router_persists_redaction_safe_circuit_state(tmp_path) -> None:
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
            )
        ],
        max_attempts_per_provider=1,
        max_total_attempts=1,
    )
    provider = FakeModelProvider(
        ProviderCapabilities(),
        [ProviderFailure(kind=FailureKind.PROVIDER_UNAVAILABLE, message="down sk-secret")],
    )
    store = FileCircuitStore(tmp_path / "provider-health.json")

    result = await ModelRouter(config, {"groq_fast": provider}, circuit_store=store).complete(
        request
    )
    second = await ModelRouter(
        config,
        {"groq_fast": FakeModelProvider(ProviderCapabilities(), [])},
        circuit_store=store,
    ).complete(request)

    payload = (tmp_path / "provider-health.json").read_text(encoding="utf-8")
    assert result.status == "incomplete_model_unavailable"
    assert second.skipped[0].skip_reason == "circuit_open"
    assert "provider_unavailable" in payload
    assert "sk-secret" not in payload
