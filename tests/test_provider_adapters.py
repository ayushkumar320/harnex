import time
from types import SimpleNamespace

import pytest

from agentharness.provider_adapters import (
    HuggingFaceProvider,
    OpenAICompatibleProvider,
    build_configured_providers,
    classify_provider_error,
)
from agentharness.providers import (
    DataPolicy,
    FailureKind,
    ModelRequest,
    ModelRouter,
    ProviderFailureException,
    ProviderKind,
    ProviderLocality,
    RouteEntry,
    RouterConfig,
    build_manifest,
)


class ChatCompletions:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def create(self, **kwargs):
        if self.error:
            raise self.error
        self.kwargs = kwargs
        return self.result


class OpenAIClient:
    def __init__(self, completions: ChatCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


class HFClient:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def chat_completion(self, **kwargs):
        if self.error:
            raise self.error
        self.kwargs = kwargs
        return self.result


class StatusError(Exception):
    def __init__(self, status_code: int, message: str = "provider error", headers=None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers or {}


def request() -> ModelRequest:
    return ModelRequest(
        messages=[{"role": "user", "content": "hello"}],
        model="demo",
        evidence_manifest=build_manifest(
            data_policy=DataPolicy.REMOTE_ALLOWED,
            local_evidence_ids=["local:1"],
        ),
    )


@pytest.mark.asyncio
async def test_openai_compatible_adapter_normalizes_response() -> None:
    result = SimpleNamespace(
        id="req-1",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="ok"),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=4),
    )
    completions = ChatCompletions(result=result)
    provider = OpenAICompatibleProvider(client=OpenAIClient(completions))

    response = await provider.complete(request())

    assert response.content == "ok"
    assert response.provider_request_id == "req-1"
    assert response.token_usage.input_tokens == 3
    assert completions.kwargs["model"] == "demo"


@pytest.mark.asyncio
async def test_huggingface_adapter_uses_chat_completion_boundary() -> None:
    result = {"choices": [{"message": {"content": "hf"}, "finish_reason": "stop"}]}
    client = HFClient(result=result)

    response = await HuggingFaceProvider(client=client).complete(request())

    assert response.content == "hf"
    assert client.kwargs["messages"][0]["content"] == "hello"


def test_provider_error_classification_redacts_auth_and_rate_limit_details() -> None:
    auth = classify_provider_error(StatusError(401, "bad api key sk-secret"))
    rate = classify_provider_error(StatusError(429, "rate limit", {"Retry-After": "2"}))

    assert auth.kind is FailureKind.AUTHENTICATION_FAILED
    assert "sk-secret" not in auth.message
    assert rate.kind is FailureKind.RATE_LIMITED
    assert rate.retry_after_seconds == 2


@pytest.mark.asyncio
async def test_adapter_raises_normalized_failure_for_malformed_response() -> None:
    provider = OpenAICompatibleProvider(
        client=OpenAIClient(ChatCompletions(result={"choices": []}))
    )

    with pytest.raises(ProviderFailureException) as exc_info:
        await provider.complete(request())

    assert exc_info.value.failure.kind is FailureKind.MALFORMED_RESPONSE


def test_provider_factory_leaves_missing_remote_credentials_unregistered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    config = RouterConfig(
        enabled=True,
        data_policy=DataPolicy.REMOTE_ALLOWED,
        route=[
            RouteEntry(
                id="groq_fast",
                provider=ProviderKind.GROQ,
                model="llama",
                locality=ProviderLocality.REMOTE,
            )
        ],
    )

    assert build_configured_providers(config) == {}


@pytest.mark.asyncio
async def test_router_deadline_bounds_blocking_synchronous_sdk_call() -> None:
    result = SimpleNamespace(
        id="late",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="too late"),
                finish_reason="stop",
            )
        ],
        usage=None,
    )

    class BlockingCompletions(ChatCompletions):
        def create(self, **kwargs):
            time.sleep(0.25)
            return result

    config = RouterConfig(
        enabled=True,
        data_policy=DataPolicy.REMOTE_ALLOWED,
        route=[
            RouteEntry(
                id="blocking",
                provider=ProviderKind.OPENAI_COMPATIBLE,
                model="demo",
                locality=ProviderLocality.REMOTE,
            )
        ],
        deadlines={"attempt_seconds": 0.02, "operation_seconds": 0.1},
        max_attempts_per_provider=1,
        max_total_attempts=1,
    )
    provider = OpenAICompatibleProvider(client=OpenAIClient(BlockingCompletions(result=result)))
    started = time.monotonic()

    routed = await ModelRouter(config, {"blocking": provider}).complete(request())

    elapsed = time.monotonic() - started
    assert routed.status == "incomplete_model_unavailable"
    assert routed.attempts[0].failure_kind is FailureKind.TIMEOUT_BEFORE_RESPONSE
    assert elapsed < 0.15
