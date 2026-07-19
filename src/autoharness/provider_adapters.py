"""Concrete provider adapter boundaries with injectable clients for tests."""

from __future__ import annotations

import asyncio
import inspect
import os
import time
from typing import Any

import httpx

from autoharness.providers import (
    FailureKind,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    ProviderFailure,
    ProviderFailureException,
    ProviderKind,
    ProviderLocality,
    RouterConfig,
    TokenUsage,
)


class OpenAICompatibleProvider:
    def __init__(self, *, client: Any, structured_json: bool = True) -> None:
        self.client = client
        self._capabilities = ProviderCapabilities(
            structured_json=structured_json,
            json_schema=structured_json,
            token_accounting=True,
        )

    async def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    async def complete(self, request: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        try:
            result = await _call_client(
                self.client.chat.completions.create,
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_output_tokens,
            )
        except Exception as exc:
            raise ProviderFailureException(classify_provider_error(exc)) from exc
        return _openai_like_response(result, started)


class GroqProvider(OpenAICompatibleProvider):
    pass


class HuggingFaceProvider:
    def __init__(self, *, client: Any) -> None:
        self.client = client
        self._capabilities = ProviderCapabilities(
            structured_json=False,
            json_schema=False,
            token_accounting=False,
        )

    async def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    async def complete(self, request: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        try:
            result = await _call_client(
                self.client.chat_completion,
                messages=request.messages,
                model=request.model,
                max_tokens=request.max_output_tokens,
                temperature=request.temperature,
            )
        except Exception as exc:
            raise ProviderFailureException(classify_provider_error(exc)) from exc
        return _openai_like_response(result, started)


def build_configured_providers(config: RouterConfig) -> dict[str, object]:
    """Instantiate configured providers from env-backed credentials.

    Missing credentials or missing local endpoints simply leave the route unregistered so the
    router can record `provider_not_registered` without making a request.
    """

    providers: dict[str, object] = {}
    for entry in config.route:
        if entry.provider is ProviderKind.GROQ:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                continue
            from groq import Groq

            providers[entry.id] = GroqProvider(
                client=Groq(api_key=api_key, timeout=config.attempt_seconds)
            )
        elif entry.provider is ProviderKind.HUGGINGFACE:
            token = os.environ.get("HF_TOKEN")
            if entry.locality is ProviderLocality.REMOTE and not token:
                continue
            from huggingface_hub import InferenceClient

            providers[entry.id] = HuggingFaceProvider(
                client=InferenceClient(
                    model=entry.model,
                    token=token,
                    base_url=entry.base_url,
                    timeout=config.attempt_seconds,
                )
            )
        elif entry.provider is ProviderKind.OPENAI_COMPATIBLE:
            api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
            if entry.locality is ProviderLocality.REMOTE and not api_key:
                continue
            if entry.base_url is None:
                continue
            from openai import OpenAI

            providers[entry.id] = OpenAICompatibleProvider(
                client=OpenAI(
                    api_key=api_key or "not-needed-for-local-endpoint",
                    base_url=entry.base_url,
                    timeout=config.attempt_seconds,
                )
            )
    return providers


async def _call_client(method: Any, **kwargs: Any) -> Any:
    """Call async SDK methods directly and isolate synchronous SDK methods from the event loop."""

    if inspect.iscoroutinefunction(method):
        return await method(**kwargs)
    result = await asyncio.to_thread(method, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def classify_provider_error(error: Exception) -> ProviderFailure:
    status_code = getattr(error, "status_code", None)
    retry_after = _retry_after(error)
    text = f"{error.__class__.__name__}: {error}"
    lowered = text.lower()
    if isinstance(error, TimeoutError | httpx.TimeoutException) or "timeout" in lowered:
        return ProviderFailure(
            kind=FailureKind.TIMEOUT_BEFORE_RESPONSE,
            message="Provider timed out before returning a response.",
        )
    if status_code == 401 or status_code == 403 or "auth" in lowered or "api key" in lowered:
        return ProviderFailure(
            kind=FailureKind.AUTHENTICATION_FAILED,
            message="Provider authentication failed.",
        )
    if status_code == 429 or "rate limit" in lowered:
        return ProviderFailure(
            kind=FailureKind.RATE_LIMITED,
            message="Provider rate limit exceeded.",
            retry_after_seconds=retry_after,
        )
    if status_code in {500, 502, 503, 504} or "unavailable" in lowered:
        return ProviderFailure(
            kind=FailureKind.PROVIDER_UNAVAILABLE,
            message="Provider is unavailable.",
            retry_after_seconds=retry_after,
        )
    if status_code == 400 or "invalid" in lowered:
        return ProviderFailure(
            kind=FailureKind.INVALID_REQUEST,
            message="Provider rejected the normalized request.",
        )
    return ProviderFailure(
        kind=FailureKind.MALFORMED_RESPONSE,
        message="Provider returned an unsupported or malformed response.",
    )


def _openai_like_response(result: Any, started: float) -> ModelResponse:
    choice = _first_choice(result)
    content = _message_content(choice)
    finish_reason = str(_get(choice, "finish_reason") or "unknown")
    usage = _get(result, "usage")
    return ModelResponse(
        content=content,
        finish_reason=finish_reason,
        latency_ms=int((time.monotonic() - started) * 1000),
        provider_request_id=_get(result, "id"),
        token_usage=TokenUsage(
            input_tokens=_usage_value(usage, "prompt_tokens", "input_tokens"),
            output_tokens=_usage_value(usage, "completion_tokens", "output_tokens"),
        ),
    )


def _first_choice(result: Any) -> Any:
    choices = _get(result, "choices")
    if not choices:
        raise ProviderFailureException(
            ProviderFailure(
                kind=FailureKind.MALFORMED_RESPONSE,
                message="Provider response did not include choices.",
            )
        )
    return choices[0]


def _message_content(choice: Any) -> str:
    message = _get(choice, "message")
    content = _get(message, "content") if message is not None else _get(choice, "text")
    if not isinstance(content, str):
        raise ProviderFailureException(
            ProviderFailure(
                kind=FailureKind.MALFORMED_RESPONSE,
                message="Provider response did not include text content.",
            )
        )
    return content


def _usage_value(usage: Any, *names: str) -> int | None:
    for name in names:
        value = _get(usage, name)
        if isinstance(value, int):
            return value
    return None


def _retry_after(error: Exception) -> float | None:
    headers = getattr(error, "headers", None)
    if not headers:
        return None
    value = headers.get("retry-after") or headers.get("Retry-After")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
