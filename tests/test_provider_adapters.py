from types import SimpleNamespace

import pytest

from autoharness.provider_adapters import (
    HuggingFaceProvider,
    OpenAICompatibleProvider,
    classify_provider_error,
)
from autoharness.providers import (
    DataPolicy,
    FailureKind,
    ModelRequest,
    ProviderFailureException,
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
