from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select

from app.ai.provider import ModelProvider, ProviderResult, StreamEvent, Usage
from app.config import get_settings
from app.models import KnowledgeChunk, KnowledgeDocument, Message
from app.services.rag import (
    embed_missing_chunks,
    embedding_signature,
    heading_boost,
    lexical_boost,
    parse_knowledge_file,
    retrieve,
    seed_knowledge_metadata,
)
from conftest import register


class FakeProvider(ModelProvider):
    def __init__(self):
        self.last_stream_messages = []
        self.last_embed_texts = []
        self.last_embed_input_type = None

    async def generate(self, messages, *, max_tokens=None):
        return ProviderResult(content="UVB 與曬背建議", usage=Usage(20, 6), request_id="fake-title", latency_ms=2)

    async def stream_generate(self, messages, *, max_tokens=None) -> AsyncIterator[StreamEvent]:
        self.last_stream_messages = messages
        yield StreamEvent(kind="token", content="請先確認 UVB 距離，")
        yield StreamEvent(kind="token", content="並量測曬背區溫度。")
        yield StreamEvent(kind="usage", usage=Usage(100, 20))
        yield StreamEvent(kind="done")

    async def vision_generate(self, messages):
        return await self.generate(messages)

    async def embed(self, texts, *, input_type="query"):
        self.last_embed_texts = texts
        self.last_embed_input_type = input_type
        return [[1.0, 0.0] for _ in texts]


def seed_document(db_session):
    document = KnowledgeDocument(
        slug="uvb-test",
        title="UVB 測試指南",
        description="測試",
        source_url="https://example.com/uvb",
        source_name="測試來源",
        reviewed_at="2026-08-12",
        tags=["UVB"],
        content_hash="abc",
    )
    db_session.add(document); db_session.flush()
    chunk = KnowledgeChunk(
        document_id=document.id,
        chunk_index=0,
        section="距離",
        content="UVB 燈具距離需要依產品規格調整。",
        embedding=[1.0, 0.0],
        embedding_model=embedding_signature(get_settings().ai_embedding_model),
    )
    db_session.add(chunk); db_session.commit()
    return document, chunk


def test_lexical_boost_rewards_domain_terms():
    assert lexical_boost("UVB 燈怎麼安裝？", "UVB 照明與更換\n安裝位置") > 0
    assert heading_boost("UVB 燈怎麼安裝？", "UVB 照明與更換") >= 0.18
    assert lexical_boost("UVB 燈怎麼安裝？", "汽車輪胎保養") == 0


def test_plain_markdown_can_be_indexed_and_removed(db_session, tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    document_path = knowledge_dir / "policies" / "leave.md"
    document_path.parent.mkdir()
    document_path.write_text("# 請假辦法\n\n員工應先完成線上申請。", encoding="utf-8")

    meta, content = parse_knowledge_file(document_path)
    assert meta["title"] == "請假辦法"
    assert meta["source_url"] == ""
    assert "線上申請" in content
    assert seed_knowledge_metadata(db_session, knowledge_dir) == 1
    saved = db_session.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == "policies-leave"))
    assert saved and saved.is_active is True

    document_path.unlink()
    assert seed_knowledge_metadata(db_session, knowledge_dir) == 0
    db_session.refresh(saved)
    assert saved.is_active is False


@pytest.mark.asyncio
async def test_rag_found_and_not_found(db_session):
    document, _ = seed_document(db_session)
    results, _ = await retrieve(db_session, FakeProvider(), get_settings(), "UVB 距離")
    assert results and results[0].document.id == document.id
    settings = get_settings().model_copy(update={"rag_min_score": 1.1})
    empty, _ = await retrieve(db_session, FakeProvider(), settings, "沒有結果")
    assert empty == []


@pytest.mark.asyncio
async def test_embedding_model_change_rebuilds_vectors(db_session):
    _, chunk = seed_document(db_session)
    chunk.embedding_model = "retired/model"
    db_session.commit()

    current_model = get_settings().ai_embedding_model
    provider = FakeProvider()
    count = await embed_missing_chunks(db_session, provider, current_model)

    assert count == 1
    assert chunk.embedding_model == embedding_signature(current_model)
    assert provider.last_embed_input_type == "passage"
    assert "UVB 測試指南" in provider.last_embed_texts[0]


def test_streaming_persists_context_and_citation(client, db_session, monkeypatch):
    seed_document(db_session)
    csrf = register(client)
    fake = FakeProvider()
    monkeypatch.setattr("app.services.chat.get_provider", lambda _settings: fake)
    conversation = client.post("/api/v1/conversations", json={}, headers={"X-CSRF-Token": csrf}).json()
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/stream",
        json={"content": "UVB 距離怎麼調整？", "attachment_ids": []},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert "event: token" in response.text
    assert "UVB 測試指南" in response.text
    saved = client.get(f"/api/v1/conversations/{conversation['id']}").json()
    assert len(saved["messages"]) == 2
    assert saved["title"] == "UVB 與曬背建議"
    assert saved["messages"][1]["status"] == "complete"
    assert saved["messages"][1]["citations"][0]["title"] == "UVB 測試指南"

    second = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/stream",
        json={"content": "那要多久檢查一次？", "attachment_ids": []},
        headers={"X-CSRF-Token": csrf},
    )
    assert second.status_code == 200
    assert any(message.get("role") == "assistant" and "曬背區溫度" in message.get("content", "") for message in fake.last_stream_messages)
    assert len(client.get(f"/api/v1/conversations/{conversation['id']}").json()["messages"]) == 4
