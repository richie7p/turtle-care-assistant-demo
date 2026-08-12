import httpx
import pytest
from fastapi import HTTPException

from app.ai.provider import NvidiaNimProvider, ProviderError, StreamEvent
from app.config import get_settings
from app.services.rate_limit import AIRateLimiter


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, "invalid_api_key"),
        (402, "quota_exceeded"),
        (404, "model_unavailable"),
        (410, "model_unavailable"),
        (429, "provider_rate_limited"),
        (503, "provider_unavailable"),
    ],
)
def test_provider_error_mapping(status_code, expected):
    response = httpx.Response(status_code, request=httpx.Request("POST", "https://example.com"))
    assert NvidiaNimProvider._map_error(response).code == expected


def test_provider_selects_vision_model_for_images():
    settings = get_settings().model_copy(
        update={"ai_model": "chat/model", "ai_vision_model": "vision/model"}
    )
    provider = NvidiaNimProvider(settings)
    text_payload = provider._chat_payload(
        [{"role": "user", "content": "hello"}], stream=False
    )
    vision_payload = provider._chat_payload(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
                ],
            }
        ],
        stream=False,
    )
    assert text_payload["model"] == "chat/model"
    assert vision_payload["model"] == "vision/model"


def test_provider_disables_reasoning_for_nemotron_3():
    settings = get_settings().model_copy(update={"ai_model": "nvidia/nemotron-3-nano-30b-a3b"})
    provider = NvidiaNimProvider(settings)
    payload = provider._chat_payload([{"role": "user", "content": "hello"}], stream=True)
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.asyncio
async def test_stream_retries_fallback_before_first_token(monkeypatch):
    settings = get_settings().model_copy(
        update={"ai_model": "primary/model", "ai_fallback_model": "fallback/model"}
    )
    provider = NvidiaNimProvider(settings)
    attempts: list[str] = []

    async def fake_stream(messages, *, model, max_tokens=None):
        attempts.append(model)
        if model == "primary/model":
            raise ProviderError("provider_timeout", "timeout", 504)
        yield StreamEvent(kind="token", content="ok")

    monkeypatch.setattr(provider, "_stream_with_model", fake_stream)
    events = [event async for event in provider.stream_generate([{"role": "user", "content": "hi"}])]
    assert attempts == ["primary/model", "fallback/model"]
    assert [event.content for event in events if event.kind == "token"] == ["ok"]
    assert events[-1].kind == "done"


@pytest.mark.asyncio
async def test_per_minute_rate_limit():
    settings = get_settings().model_copy(update={"ai_requests_per_minute": 1, "ai_global_concurrency": 1})
    limiter = AIRateLimiter(settings)
    async with limiter.limit("user-1"):
        pass
    with pytest.raises(HTTPException) as error:
        async with limiter.limit("user-1"):
            pass
    assert error.value.status_code == 429
