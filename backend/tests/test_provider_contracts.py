import json

import httpx
import pytest

from app.ai.provider import NvidiaNimProvider, ProviderError
from app.config import get_settings
from conftest import register


@pytest.fixture
def provider_http(monkeypatch):
    original_client = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(
            **kwargs, transport=httpx.MockTransport(handler)))
        return NvidiaNimProvider(get_settings().model_copy(update={
            "ai_api_key": "synthetic-test-key", "ai_fallback_model": None,
        }))

    return install


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [
    [],
    [{"index": 0, "embedding": []}],
    [{"index": 0, "embedding": [True, 1]}],
    [{"index": 0, "embedding": ["0.2", 1]}],
    [{"index": 4, "embedding": [0.2, 1]}],
    [{"index": 0, "embedding": [0, 0]}],
])
async def test_invalid_embedding_cannot_reach_retrieval(provider_http, data):
    provider = provider_http(lambda _: httpx.Response(200, json={"data": data}))
    with pytest.raises(ProviderError) as exc:
        await provider.embed(["synthetic query"])
    assert exc.value.code == "provider_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [
    [{"index": 0, "embedding": [1, 0]}, {"index": 0, "embedding": [0, 1]}],
    [{"index": 0, "embedding": [1, 0]}, {"index": 1, "embedding": [0, 1, 0]}],
])
async def test_embedding_batch_requires_unique_indexes_and_dimensions(provider_http, data):
    provider = provider_http(lambda _: httpx.Response(200, json={"data": data}))
    with pytest.raises(ProviderError):
        await provider.embed(["document one", "document two"], input_type="passage")


@pytest.mark.asyncio
async def test_embedding_reorders_valid_batch_without_losing_alignment(provider_http):
    provider = provider_http(lambda _: httpx.Response(200, json={"data": [
        {"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]},
    ]}))
    assert await provider.embed(["one", "two"]) == [[1, 0], [0, 1]]


@pytest.mark.asyncio
async def test_pending_embedding_has_bounded_timeout(provider_http, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request.url)
        return httpx.Response(202, json={"requestId": "synthetic-request"})
    async def no_delay(_):
        pass
    monkeypatch.setattr("app.ai.provider.asyncio.sleep", no_delay)
    provider = provider_http(handler)
    with pytest.raises(ProviderError) as exc:
        await provider.embed(["query"])
    assert exc.value.code == "provider_timeout"
    assert len(calls) == 31


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [None, {}, {"choices": []}, {"choices": [{"message": {"content": 123}}]}])
async def test_malformed_generation_becomes_safe_provider_error(provider_http, body):
    provider = provider_http(lambda _: httpx.Response(200, content=json.dumps(body)))
    with pytest.raises(ProviderError):
        await provider.generate([{"role": "user", "content": "test"}])


def event(data):
    return "data: " + json.dumps(data) + "\n\n"


@pytest.mark.asyncio
@pytest.mark.parametrize(("ending", "code"), [
    ("", "provider_interrupted"),
    (event({"choices": [{"delta": {}, "finish_reason": "length"}]}), "response_truncated"),
])
async def test_partial_stream_is_not_reported_as_complete(provider_http, ending, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, text=event({"choices": [{"delta": {"content": "partial answer"}}]}) + ending,
                              headers={"Content-Type": "text/event-stream"})
    provider = provider_http(handler)
    received = []
    with pytest.raises(ProviderError) as exc:
        async for item in provider.stream_generate([{"role": "user", "content": "test"}]):
            received.append(item)
    assert exc.value.code == code
    assert [item.content for item in received if item.kind == "token"] == ["partial answer"]
    assert not any(item.kind == "done" for item in received)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_terminal_stream_preserves_usage_and_content(provider_http):
    body = (event({"choices": [{"delta": {"content": "complete answer"}, "finish_reason": "stop"}]})
            + event({"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 0}}) + "data: [DONE]\n\n")
    provider = provider_http(lambda _: httpx.Response(200, text=body))
    received = [item async for item in provider.stream_generate([{"role": "user", "content": "test"}])]
    assert received[-1].kind == "done"
    assert next(item.usage for item in received if item.kind == "usage").output_tokens == 0


def test_invalid_embedding_degrades_with_visible_rag_status(client, monkeypatch, provider_http):
    def handler(request):
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, text=event({"choices": [{"delta": {"content": "知識庫暫時無法使用。"}, "finish_reason": "stop"}]}) + "data: [DONE]\n\n")
    provider = provider_http(handler)
    monkeypatch.setattr("app.services.chat.get_provider", lambda _: provider)
    csrf = register(client)
    headers = {"X-CSRF-Token": csrf}
    conversation = client.post("/api/v1/conversations", headers=headers, json={"title": "固定測試標題"}).json()
    url = f"/api/v1/conversations/{conversation['id']}"
    response = client.post(url + "/messages/stream", headers=headers, json={"content": "測試查詢"})
    assert response.status_code == 200
    assert '"status": "unavailable"' in response.text
    assert "event: done" in response.text
    saved = client.get(url).json()["messages"][-1]
    assert saved["status"] == "complete"
    assert saved["citations"] == []


def test_stream_disconnect_persists_partial_answer_as_interrupted(client, monkeypatch, provider_http):
    def handler(request):
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 0]}]})
        return httpx.Response(200, text=event({"choices": [{"delta": {"content": "部分回答"}}]}))
    provider = provider_http(handler)
    monkeypatch.setattr("app.services.chat.get_provider", lambda _: provider)
    csrf = register(client)
    headers = {"X-CSRF-Token": csrf}
    conversation = client.post("/api/v1/conversations", headers=headers, json={"title": "固定測試標題"}).json()
    url = f"/api/v1/conversations/{conversation['id']}"
    response = client.post(url + "/messages/stream", headers=headers, json={"content": "測試查詢"})
    assert "provider_interrupted" in response.text and "event: done" not in response.text
    saved = client.get(url).json()["messages"][-1]
    assert saved["status"] == "interrupted" and saved["content"] == "部分回答"
