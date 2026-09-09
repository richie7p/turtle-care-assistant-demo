import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select, text

from app.ai.provider import ProviderError, ProviderResult, Usage
from app.api.conversations import message_response
from app.config import get_settings
from app.models import Conversation, KnowledgeChunk, Message, MessageCitation, User
from app.services.chat import update_summary_if_needed
from app.services.rag import seed_knowledge_metadata
from app.services.rate_limit import AIRateLimiter
from conftest import register
from test_chat_rag import FakeProvider, seed_document


@pytest.mark.asyncio
async def test_cancelled_waiter_can_retry_without_over_releasing_capacity():
    limiter = AIRateLimiter(get_settings().model_copy(update={"ai_global_concurrency": 1}))
    holder = limiter.limit("holder")
    await holder.__aenter__()
    waiting = limiter.limit("waiter")
    task = asyncio.create_task(waiting.__aenter__())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    retry = limiter.limit("waiter")
    retry_task = asyncio.create_task(retry.__aenter__())
    await asyncio.sleep(0)
    assert not retry_task.done()  # Cancellation must not release holder's slot.
    await holder.__aexit__(None, None, None)
    await asyncio.wait_for(retry_task, 1)
    await retry.__aexit__(None, None, None)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "LA", "P", "1"])
def test_png_color_modes_upload_and_round_trip(client, mode):
    csrf = register(client)
    image = BytesIO()
    Image.new(mode, (16, 12)).save(image, format="PNG")
    response = client.post(
        "/api/v1/attachments", files={"file": ("sample.png", image.getvalue(), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201, response.text
    saved = client.get(f"/api/v1/attachments/{response.json()['id']}")
    assert saved.status_code == 200
    with Image.open(BytesIO(saved.content)) as decoded:
        assert decoded.format == "PNG"
        assert decoded.size == (16, 12)


def test_completed_answer_preserves_citations_after_knowledge_update(client, db_session, monkeypatch, tmp_path):
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    document, chunk = seed_document(db_session)
    old_chunk_id = chunk.id
    csrf = register(client)
    monkeypatch.setattr("app.services.chat.get_provider", lambda _: FakeProvider())
    conversation = client.post("/api/v1/conversations", json={}, headers={"X-CSRF-Token": csrf}).json()
    url = f"/api/v1/conversations/{conversation['id']}"
    response = client.post(url + "/messages/stream", json={"content": "UVB?"}, headers={"X-CSRF-Token": csrf})
    assert "event: done" in response.text
    before = client.get(url).json()["messages"][1]["citations"]
    assert len(before) == 1
    (tmp_path / "uvb-test.md").write_text("# New title\n\n# New section\nChanged advice", encoding="utf-8")
    seed_knowledge_metadata(db_session, tmp_path)
    assert db_session.scalar(select(KnowledgeChunk.id).where(KnowledgeChunk.id == old_chunk_id)) is None
    assert db_session.scalar(select(MessageCitation.id)) is None
    assert client.get(url).json()["messages"][1]["citations"] == before


class SummaryProvider:
    def __init__(self, fail_on=None):
        self.inputs = []
        self.fail_on = fail_on

    async def generate(self, messages, **kwargs):
        self.inputs.append(messages[1]["content"])
        if len(self.inputs) == self.fail_on:
            raise ProviderError("provider_timeout", "timeout", 504)
        return ProviderResult(content="updated summary", usage=Usage(1, 1), request_id="fake", latency_ms=1)


def summary_conversation(db):
    user = User(email="summary@example.com", display_name="test", password_hash="unused")
    db.add(user)
    db.flush()
    conversation = Conversation(user_id=user.id, summary="previous summary", summarized_message_count=8)
    db.add(conversation)
    db.flush()
    now = datetime.now(timezone.utc)
    for i in range(32):
        db.add(Message(
            user_id=user.id, conversation_id=conversation.id, role="user",
            content=f"[message-{i}]" + "x" * 3000,
            created_at=now + timedelta(seconds=i),
        ))
    db.commit()
    return user, conversation


@pytest.mark.asyncio
async def test_summary_batches_include_every_unseen_message(db_session):
    user, conversation = summary_conversation(db_session)
    provider = SummaryProvider()
    await update_summary_if_needed(db_session, get_settings(), provider, conversation, user.id)
    inputs = "\n".join(provider.inputs)
    for i in range(8, 20):
        assert inputs.count(f"[message-{i}]") == 1
    assert "[message-0]" not in inputs
    assert "[message-20]" not in inputs
    assert conversation.summarized_message_count == 20


@pytest.mark.asyncio
async def test_summary_failure_does_not_advance_past_successful_batch(db_session):
    user, conversation = summary_conversation(db_session)
    provider = SummaryProvider(fail_on=2)
    await update_summary_if_needed(db_session, get_settings(), provider, conversation, user.id)
    assert conversation.summarized_message_count == 13
    assert conversation.summary == "updated summary"


def test_migration_backfills_legacy_citations_before_index_replacement(tmp_path, monkeypatch):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database import Base

    database_url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        document, chunk = seed_document(db)
        user, conversation = summary_conversation(db)
        message = Message(user_id=user.id, conversation_id=conversation.id, role="assistant", content="Answer")
        db.add(message)
        db.flush()
        message_id = message.id
        db.add(MessageCitation(message_id=message_id, document_id=document.id, chunk_id=chunk.id, rank=1, score=0.9))
        db.commit()
    # Restore the exact column layout used before this migration.
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE messages DROP COLUMN citation_snapshots"))
    settings = get_settings().model_copy(update={"database_url": database_url})
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.stamp(config, "1a4f0fbd82c3")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with Session(engine) as db:
        db.execute(text("PRAGMA foreign_keys=ON"))
        message = db.get(Message, message_id)
        before = message_response(message).citations
        assert len(before) == 1
        assert before[0].title == "UVB 測試指南"
        (tmp_path / "uvb-test.md").write_text("# New title\n\nChanged content", encoding="utf-8")
        seed_knowledge_metadata(db, tmp_path)
        db.expire_all()
        assert db.scalar(select(MessageCitation.id)) is None
        assert message_response(db.get(Message, message_id)).citations == before
    engine.dispose()
