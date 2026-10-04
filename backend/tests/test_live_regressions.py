import pytest

from app.ai.provider import NvidiaNimProvider, ProviderError, StreamEvent
from app.config import get_settings
from app.services.chat import clean_generated_title


@pytest.mark.parametrize(("content", "expected"), [
    ('「知識庫測試代碼」\n\n```python\nimport pytest', "知識庫測試代碼"),
    ("# 烏龜照護\n多餘的說明", "烏龜照護"),
    ("```python\nimport pytest", ""),
    ("\n\n", ""),
    ("龜" * 25, "龜" * 18),
])
def test_generated_title_excludes_multiline_model_output(content, expected):
    assert clean_generated_title(content) == expected


def vision_messages():
    return [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
    ]}]


@pytest.mark.asyncio
async def test_empty_vision_stream_retries_before_exposing_content(monkeypatch):
    settings = get_settings().model_copy(update={"ai_vision_model": "vision/model", "ai_fallback_model": "text/fallback"})
    provider = NvidiaNimProvider(settings)
    attempts = []

    async def stream(messages, *, model, max_tokens=None):
        attempts.append(model)
        yield StreamEvent(kind="token", content="\n")
        if len(attempts) == 2:
            yield StreamEvent(kind="token", content="紅色")

    monkeypatch.setattr(provider, "_stream_with_model", stream)
    events = [event async for event in provider.stream_generate(vision_messages())]
    assert attempts == ["vision/model", "vision/model"]
    assert [event.content for event in events if event.kind == "token"] == ["\n紅色"]
    assert events[-1].kind == "done"


@pytest.mark.asyncio
async def test_repeated_empty_vision_stream_fails_after_one_retry(monkeypatch):
    provider = NvidiaNimProvider(get_settings())
    attempts = []

    async def stream(messages, *, model, max_tokens=None):
        attempts.append(model)
        yield StreamEvent(kind="token", content=" ")

    monkeypatch.setattr(provider, "_stream_with_model", stream)
    with pytest.raises(ProviderError) as exc:
        _ = [event async for event in provider.stream_generate(vision_messages())]
    assert exc.value.code == "empty_response"
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_partial_vision_answer_is_never_replayed(monkeypatch):
    provider = NvidiaNimProvider(get_settings())
    attempts = []
    visible = []

    async def stream(messages, *, model, max_tokens=None):
        attempts.append(model)
        yield StreamEvent(kind="token", content="部分答案")
        raise ProviderError("provider_timeout", "timeout", 504)

    monkeypatch.setattr(provider, "_stream_with_model", stream)
    with pytest.raises(ProviderError):
        async for event in provider.stream_generate(vision_messages()):
            if event.kind == "token":
                visible.append(event.content)
    assert len(attempts) == 1
    assert visible == ["部分答案"]
