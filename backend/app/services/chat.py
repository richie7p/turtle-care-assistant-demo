from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..ai.provider import ModelProvider, ProviderError, StreamEvent, Usage, get_provider
from ..config import Settings
from ..models import (
    Attachment,
    Conversation,
    Message,
    MessageCitation,
    Turtle,
    User,
    UserSettings,
    utcnow,
)
from .rag import RetrievedChunk, retrieve
from .rate_limit import get_ai_limiter
from .usage import estimate_tokens, save_usage


DEFAULT_SYSTEM_PROMPT = """你是 AI 知識助理。優先依據提供的知識庫回答；資料不足時必須明確說明。
不得虛構來源、政策、數值或確定性結論。使用 Markdown，先給結論，再列出依據與可執行步驟。"""


def configured_system_prompt(settings: Settings) -> str:
    if settings.system_prompt:
        return settings.system_prompt.strip()
    try:
        prompt = settings.system_prompt_path.read_text(encoding="utf-8").strip()
        return prompt or DEFAULT_SYSTEM_PROMPT
    except OSError:
        return DEFAULT_SYSTEM_PROMPT


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def turtle_context(turtle: Turtle | None) -> str:
    if not turtle:
        return "未選擇烏龜 Profile，請提供一般性建議並提醒不同物種需求可能不同。"
    sex_label = {"male": "公", "female": "母", "unknown": "未知"}.get(turtle.sex, "未知")
    placement_label = {"indoor": "室內", "outdoor": "室外"}.get(turtle.placement or "", "未填")
    values = [
        f"名稱：{turtle.name}",
        f"種類：{turtle.species}",
        f"類型：{'水龜' if turtle.turtle_type == 'aquatic' else '陸龜'}",
        f"年齡：{turtle.age or '未填'}",
        f"性別：{sex_label}",
        f"背甲長度：{turtle.shell_length_cm or '未填'} cm",
        f"體重：{turtle.weight_g or '未填'} g",
        f"飼養環境：{turtle.habitat or '未填'}",
        f"位置：{placement_label}",
        f"飼養箱尺寸：{turtle.enclosure_size or '未填'}",
        f"UVB：{'有' if turtle.has_uvb else '無' if turtle.has_uvb is False else '未填'}",
        f"加熱設備：{'有' if turtle.has_heater else '無' if turtle.has_heater is False else '未填'}",
        f"飲食：{turtle.diet or '未填'}",
        f"備註：{turtle.notes or '無'}",
    ]
    return "\n".join(values)


def rag_context(results: list[RetrievedChunk]) -> str:
    if not results:
        return "本次知識庫沒有達到相關性門檻的資料。不可假裝有引用來源。"
    return "\n\n".join(
        f"[來源 {item.rank}] {item.document.title}｜{item.chunk.section}\n{item.chunk.content}"
        for item in results
    )


def citation_payload(results: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        {
            "document_id": item.document.id,
            "chunk_id": item.chunk.id,
            "title": item.document.title,
            "source_name": item.document.source_name,
            "source_url": item.document.source_url,
            "section": item.chunk.section,
            "rank": item.rank,
            "score": round(item.score, 4),
        }
        for item in results
    ]


def attachment_data_url(settings: Settings, attachment: Attachment) -> str:
    path = (Path(settings.upload_dir) / attachment.storage_key).resolve()
    if Path(settings.upload_dir).resolve() not in path.parents or not path.is_file():
        raise ProviderError("missing_attachment", "找不到其中一張已上傳圖片。", 422)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{attachment.media_type};base64,{encoded}"


def build_model_messages(
    db: Session,
    settings: Settings,
    conversation: Conversation,
    current_message: Message,
    content: str,
    attachments: list[Attachment],
    rag_results: list[RetrievedChunk],
) -> list[dict[str, Any]]:
    turtle = None
    if settings.enable_turtle_module and conversation.turtle_id:
        turtle = db.scalar(
            select(Turtle).where(Turtle.id == conversation.turtle_id, Turtle.user_id == conversation.user_id)
        )
    user_settings = db.get(UserSettings, conversation.user_id)
    style = (user_settings.response_style if user_settings else "balanced")
    style_label = {"concise": "精簡", "balanced": "適中", "detailed": "詳細"}.get(style, "適中")
    sections = [
        configured_system_prompt(settings),
        f"回覆詳細度：{style_label}",
    ]
    if settings.enable_turtle_module:
        sections.append(f"【目前烏龜資料】\n{turtle_context(turtle)}")
    sections.extend(
        [
            f"【對話摘要】\n{conversation.summary or '尚無摘要'}",
            f"【知識庫檢索】\n{rag_context(rag_results)}",
        ]
    )
    system = "\n\n".join(sections)
    recent = list(
        db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.user_id == conversation.user_id,
                Message.id != current_message.id,
                Message.status == "complete",
            )
            .order_by(Message.created_at.desc())
            .limit(settings.context_recent_messages)
        )
    )
    recent.reverse()
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for message in recent:
        messages.append({"role": message.role, "content": message.content})

    if attachments:
        current_content: list[dict[str, Any]] = [{"type": "text", "text": content}]
        current_content.extend(
            {"type": "image_url", "image_url": {"url": attachment_data_url(settings, attachment)}}
            for attachment in attachments
        )
        messages.append({"role": "user", "content": current_content})
    else:
        messages.append({"role": "user", "content": content})

    while sum(len(str(item.get("content", ""))) for item in messages) > settings.context_max_chars and len(messages) > 2:
        messages.pop(1)
    return messages


async def update_title_if_needed(
    db: Session,
    settings: Settings,
    provider: ModelProvider,
    conversation: Conversation,
    user_id: str,
    first_question: str,
) -> None:
    if conversation.title != "新對話":
        return
    fallback = first_question.strip().replace("\n", " ")[:28] or f"{settings.app_name}問題"
    started = time.perf_counter()
    request_id = f"title-{uuid.uuid4()}"
    try:
        result = await provider.generate(
            [
                {"role": "system", "content": "將問題濃縮成不超過18個繁體中文字的對話標題，只輸出標題。"},
                {"role": "user", "content": first_question[:1000]},
            ],
            max_tokens=40,
        )
        title = result.content.strip().strip('"「」')[:40]
        conversation.title = title or fallback
        save_usage(
            db,
            settings,
            request_id=request_id,
            user_id=user_id,
            feature="title",
            model=settings.ai_model,
            usage=result.usage,
            latency_ms=result.latency_ms,
        )
    except ProviderError as exc:
        conversation.title = fallback
        save_usage(
            db,
            settings,
            request_id=request_id,
            user_id=user_id,
            feature="title",
            model=settings.ai_model,
            usage=Usage(),
            latency_ms=round((time.perf_counter() - started) * 1000),
            status="error",
            error_code=exc.code,
        )
    db.commit()


async def update_summary_if_needed(
    db: Session, settings: Settings, provider: ModelProvider, conversation: Conversation, user_id: str
) -> None:
    count = db.scalar(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation.id,
            Message.user_id == user_id,
            Message.status == "complete",
        )
    ) or 0
    if count < settings.summary_trigger_messages or count - conversation.summarized_message_count < 8:
        return
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.user_id == user_id, Message.status == "complete")
            .order_by(Message.created_at)
        )
    )
    transcript = "\n".join(f"{m.role}: {m.content}" for m in messages[:-settings.context_recent_messages])
    if not transcript:
        return
    request_id = f"summary-{uuid.uuid4()}"
    try:
        result = await provider.generate(
            [
                {"role": "system", "content": "整理對話摘要，保留使用者提供的背景資料、已給建議、未解問題與重要數值，300字內。"},
                {"role": "user", "content": f"舊摘要：{conversation.summary or '無'}\n\n新對話：\n{transcript[:16000]}"},
            ],
            max_tokens=400,
        )
        conversation.summary = result.content.strip()
        conversation.summarized_message_count = max(0, count - settings.context_recent_messages)
        save_usage(
            db,
            settings,
            request_id=request_id,
            user_id=user_id,
            feature="summary",
            model=settings.ai_model,
            usage=result.usage,
            latency_ms=result.latency_ms,
        )
        db.commit()
    except ProviderError:
        db.rollback()


async def stream_chat_response(
    db: Session,
    settings: Settings,
    user: User,
    conversation: Conversation,
    content: str,
    attachments: list[Attachment],
) -> AsyncIterator[str]:
    provider = get_provider(settings)
    limiter = get_ai_limiter(settings)
    conversation = db.merge(conversation)
    request_id = f"chat-{uuid.uuid4()}"
    user_message = Message(user_id=user.id, conversation_id=conversation.id, role="user", content=content)
    assistant_message = Message(
        user_id=user.id, conversation_id=conversation.id, role="assistant", content="", status="streaming"
    )
    db.add_all([user_message, assistant_message])
    db.flush()
    for attachment in attachments:
        attachment.message_id = user_message.id
        attachment.conversation_id = conversation.id
    conversation.updated_at = utcnow()
    db.commit()
    yield sse(
        "meta",
        {
            "request_id": request_id,
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
        },
    )

    content_parts: list[str] = []
    usage = Usage()
    used_model = settings.ai_vision_model if attachments else settings.ai_model
    started = time.perf_counter()
    try:
        async with limiter.limit(user.id):
            rag_results: list[RetrievedChunk] = []
            rag_status = "no_results"
            rag_request_id = f"rag-{uuid.uuid4()}"
            rag_started = time.perf_counter()
            try:
                rag_results, query_chars = await retrieve(db, provider, settings, content)
                rag_status = "found" if rag_results else "no_results"
                save_usage(
                    db,
                    settings,
                    request_id=rag_request_id,
                    user_id=user.id,
                    feature="rag",
                    model=settings.ai_embedding_model,
                    usage=Usage(input_tokens=estimate_tokens(content), output_tokens=0, estimated=True),
                    latency_ms=round((time.perf_counter() - rag_started) * 1000),
                )
            except ProviderError as exc:
                rag_status = "unavailable"
                save_usage(
                    db,
                    settings,
                    request_id=rag_request_id,
                    user_id=user.id,
                    feature="rag",
                    model=settings.ai_embedding_model,
                    usage=Usage(),
                    latency_ms=round((time.perf_counter() - rag_started) * 1000),
                    status="error",
                    error_code=exc.code,
                )

            citations = citation_payload(rag_results)
            yield sse("citations", {"status": rag_status, "items": citations})
            model_messages = build_model_messages(
                db, settings, conversation, user_message, content, attachments, rag_results
            )
            async for event in provider.stream_generate(model_messages):
                if event.kind == "model" and event.content:
                    used_model = event.content
                elif event.kind == "token" and event.content:
                    content_parts.append(event.content)
                    yield sse("token", {"delta": event.content})
                elif event.kind == "usage" and event.usage:
                    usage = event.usage

            final_content = "".join(content_parts).strip()
            if not final_content:
                raise ProviderError("empty_response", "AI 沒有產生內容，請再試一次。", 503)
            assistant_message.content = final_content
            assistant_message.status = "complete"
            for item in rag_results:
                db.add(
                    MessageCitation(
                        message_id=assistant_message.id,
                        document_id=item.document.id,
                        chunk_id=item.chunk.id,
                        rank=item.rank,
                        score=item.score,
                    )
                )
            conversation.updated_at = utcnow()
            db.commit()

            if usage.input_tokens is None:
                usage = Usage(
                    input_tokens=estimate_tokens(json.dumps(model_messages, ensure_ascii=False)),
                    output_tokens=estimate_tokens(final_content),
                    estimated=True,
                )
            save_usage(
                db,
                settings,
                request_id=request_id,
                user_id=user.id,
                feature="vision" if attachments else "chat",
                model=used_model,
                usage=usage,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
            await update_title_if_needed(db, settings, provider, conversation, user.id, content)
            await update_summary_if_needed(db, settings, provider, conversation, user.id)
            yield sse(
                "usage",
                {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "estimated": usage.estimated,
                },
            )
            yield sse("done", {"conversation_title": conversation.title, "message_id": assistant_message.id})
    except ProviderError as exc:
        assistant_message.content = "".join(content_parts).strip()
        assistant_message.status = "interrupted" if content_parts else "error"
        db.commit()
        save_usage(
            db,
            settings,
            request_id=request_id,
            user_id=user.id,
            feature="vision" if attachments else "chat",
            model=used_model,
            usage=usage,
            latency_ms=round((time.perf_counter() - started) * 1000),
            status="error",
            error_code=exc.code,
        )
        yield sse("error", {"code": exc.code, "message": exc.friendly_message})
    except HTTPException as exc:
        assistant_message.status = "error"
        db.commit()
        yield sse("error", {"code": "request_limited", "message": str(exc.detail)})
