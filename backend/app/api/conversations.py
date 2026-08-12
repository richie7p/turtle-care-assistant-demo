from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from ..config import get_settings
from ..dependencies import CSRFSession, CurrentUser, DB
from ..models import Attachment, Conversation, Message, MessageCitation, Turtle
from ..schemas import (
    AttachmentResponse,
    ChatRequest,
    CitationResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from ..services.chat import stream_chat_response
from ..services.uploads import delete_attachment_file


router = APIRouter(prefix="/conversations", tags=["conversations"])


def conversation_response(db: DB, conversation: Conversation) -> ConversationResponse:
    turtle_name = None
    if conversation.turtle_id:
        turtle_name = db.scalar(
            select(Turtle.name).where(
                Turtle.id == conversation.turtle_id,
                Turtle.user_id == conversation.user_id,
            )
        )
    return ConversationResponse.model_validate(conversation).model_copy(update={"turtle_name": turtle_name})


def message_response(message: Message) -> MessageResponse:
    attachments = [
        AttachmentResponse.model_validate(item).model_copy(update={"url": f"/api/v1/attachments/{item.id}"})
        for item in message.attachments
    ]
    citations = [
        CitationResponse(
            document_id=item.document_id,
            chunk_id=item.chunk_id,
            title=item.document.title,
            source_name=item.document.source_name,
            source_url=item.document.source_url,
            section=item.chunk.section,
            rank=item.rank,
            score=item.score,
        )
        for item in sorted(message.citations, key=lambda citation: citation.rank)
    ]
    return MessageResponse(
        id=message.id,
        user_id=message.user_id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        status=message.status,
        created_at=message.created_at,
        attachments=attachments,
        citations=citations,
    )


def get_owned_conversation(db: DB, user_id: str, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="找不到這個對話。")
    return conversation


@router.get("", response_model=list[ConversationResponse])
def list_conversations(db: DB, user: CurrentUser):
    conversations = db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    ).all()
    return [conversation_response(db, item) for item in conversations]


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate, db: DB, user: CurrentUser, _csrf: CSRFSession):
    if payload.turtle_id and not db.scalar(
        select(Turtle.id).where(Turtle.id == payload.turtle_id, Turtle.user_id == user.id)
    ):
        raise HTTPException(status_code=404, detail="找不到指定的烏龜。")
    conversation = Conversation(
        user_id=user.id,
        turtle_id=payload.turtle_id,
        title=(payload.title or "新對話").strip(),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation_response(db, conversation)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, db: DB, user: CurrentUser):
    conversation = db.scalar(
        select(Conversation)
        .options(
            selectinload(Conversation.messages).selectinload(Message.attachments),
            selectinload(Conversation.messages).selectinload(Message.citations).joinedload(MessageCitation.document),
            selectinload(Conversation.messages).selectinload(Message.citations).joinedload(MessageCitation.chunk),
        )
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="找不到這個對話。")
    base = conversation_response(db, conversation).model_dump()
    base["messages"] = [message_response(message) for message in conversation.messages]
    return ConversationDetail.model_validate(base)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    db: DB,
    user: CurrentUser,
    _csrf: CSRFSession,
):
    conversation = get_owned_conversation(db, user.id, conversation_id)
    data = payload.model_dump(exclude_unset=True)
    if "turtle_id" in data and data["turtle_id"] is not None:
        if not db.scalar(select(Turtle.id).where(Turtle.id == data["turtle_id"], Turtle.user_id == user.id)):
            raise HTTPException(status_code=404, detail="找不到指定的烏龜。")
    for key, value in data.items():
        setattr(conversation, key, value.strip() if key == "title" and value else value)
    db.commit()
    db.refresh(conversation)
    return conversation_response(db, conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, db: DB, user: CurrentUser, _csrf: CSRFSession):
    conversation = get_owned_conversation(db, user.id, conversation_id)
    settings = get_settings()
    attachments = list(
        db.scalars(
            select(Attachment).where(
                Attachment.conversation_id == conversation.id,
                Attachment.user_id == user.id,
            )
        )
    )
    for attachment in attachments:
        delete_attachment_file(settings, attachment)
    db.delete(conversation)
    db.commit()
    return None


@router.post("/{conversation_id}/messages/stream")
def send_message(
    conversation_id: str,
    payload: ChatRequest,
    db: DB,
    user: CurrentUser,
    _csrf: CSRFSession,
):
    settings = get_settings()
    if len(payload.content) > settings.max_input_chars:
        raise HTTPException(status_code=422, detail=f"單次訊息不可超過 {settings.max_input_chars} 字。")
    if len(payload.attachment_ids) > settings.max_images_per_message:
        raise HTTPException(status_code=422, detail=f"每則訊息最多 {settings.max_images_per_message} 張圖片。")
    conversation = get_owned_conversation(db, user.id, conversation_id)
    attachments: list[Attachment] = []
    if payload.attachment_ids:
        attachments = list(
            db.scalars(
                select(Attachment).where(
                    Attachment.id.in_(payload.attachment_ids),
                    Attachment.user_id == user.id,
                    Attachment.message_id.is_(None),
                )
            )
        )
        if len(attachments) != len(set(payload.attachment_ids)):
            raise HTTPException(status_code=404, detail="部分圖片不存在或已被使用。")
        if any(item.conversation_id not in (None, conversation.id) for item in attachments):
            raise HTTPException(status_code=403, detail="圖片不屬於這個對話。")
    generator = stream_chat_response(db, settings, user, conversation, payload.content.strip(), attachments)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
