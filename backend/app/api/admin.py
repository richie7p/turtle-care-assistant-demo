from datetime import datetime, timezone
import time

import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import case, delete, func, or_, select

from ..ai.provider import ProviderError, get_provider
from ..config import get_settings
from ..dependencies import AdminUser, CSRFSession, DB
from ..models import (
    AIUsageLog,
    AdminAuditLog,
    Conversation,
    KnowledgeChunk,
    KnowledgeDocument,
    Message,
    SessionRecord,
    Turtle,
    User,
)
from ..schemas import (
    AdminAuditItem,
    AdminAuditListResponse,
    AdminKnowledgeItem,
    AdminKnowledgeStatusResponse,
    AdminKnowledgeSyncResponse,
    AdminProviderHealthResponse,
    AdminStatsResponse,
    AdminSystemInfoResponse,
    AdminUsageItem,
    AdminUsageListResponse,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserUpdate,
)
from ..services.rag import embed_missing_chunks, embedding_signature, seed_knowledge_metadata


router = APIRouter(prefix="/admin", tags=["admin"])


def save_audit(
    db: DB,
    actor: User,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        )
    )


@router.get("/stats", response_model=AdminStatsResponse)
def admin_stats(db: DB, _admin: AdminUser):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    admins = db.scalar(
        select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True))
    ) or 0
    turtles = db.scalar(select(func.count(Turtle.id))) or 0
    conversations = db.scalar(select(func.count(Conversation.id))) or 0
    messages = db.scalar(select(func.count(Message.id))) or 0
    conversations_today = db.scalar(
        select(func.count(Conversation.id)).where(Conversation.created_at >= today)
    ) or 0
    ai_requests_today = db.scalar(
        select(func.count(AIUsageLog.id)).where(AIUsageLog.created_at >= today)
    ) or 0
    ai_errors_today = db.scalar(
        select(func.count(AIUsageLog.id)).where(
            AIUsageLog.created_at >= today, AIUsageLog.status != "success"
        )
    ) or 0
    input_tokens, output_tokens, cost = db.execute(
        select(
            func.coalesce(func.sum(AIUsageLog.input_tokens), 0),
            func.coalesce(func.sum(AIUsageLog.output_tokens), 0),
            func.sum(AIUsageLog.estimated_cost),
        ).where(AIUsageLog.created_at >= today)
    ).one()
    features = {
        feature: count
        for feature, count in db.execute(
            select(AIUsageLog.feature, func.count(AIUsageLog.id))
            .where(AIUsageLog.created_at >= today)
            .group_by(AIUsageLog.feature)
        ).all()
    }
    last_success = db.scalar(
        select(AIUsageLog)
        .where(AIUsageLog.status == "success")
        .order_by(AIUsageLog.created_at.desc())
        .limit(1)
    )
    knowledge_documents = db.scalar(
        select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.is_active.is_(True))
    ) or 0
    knowledge_chunks = db.scalar(
        select(func.count(KnowledgeChunk.id))
        .join(KnowledgeDocument)
        .where(KnowledgeDocument.is_active.is_(True))
    ) or 0
    embedded_chunks = db.scalar(
        select(func.count(KnowledgeChunk.id))
        .join(KnowledgeDocument)
        .where(
            KnowledgeDocument.is_active.is_(True),
            KnowledgeChunk.embedding.is_not(None),
            KnowledgeChunk.embedding_model == embedding_signature(settings.ai_embedding_model),
        )
    ) or 0
    cost_configured = (
        settings.ai_input_cost_per_million is not None
        and settings.ai_output_cost_per_million is not None
    )
    return AdminStatsResponse(
        users=users,
        active_users=active_users,
        admins=admins,
        turtles=turtles,
        conversations=conversations,
        message_count=messages,
        conversations_today=conversations_today,
        ai_requests_today=ai_requests_today,
        ai_errors_today=ai_errors_today,
        ai_success_rate_today=(
            round((ai_requests_today - ai_errors_today) / ai_requests_today * 100, 1)
            if ai_requests_today
            else None
        ),
        input_tokens_today=input_tokens,
        output_tokens_today=output_tokens,
        estimated_cost_today=cost if cost_configured else None,
        cost_configured=cost_configured,
        feature_usage=features,
        model=settings.ai_model,
        vision_model=settings.ai_vision_model,
        embedding_model=settings.ai_embedding_model,
        configured=bool(settings.ai_api_key),
        last_success_at=last_success.created_at if last_success else None,
        last_latency_ms=last_success.latency_ms if last_success else None,
        knowledge_documents=knowledge_documents,
        knowledge_chunks=knowledge_chunks,
        embedded_chunks=embedded_chunks,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    db: DB,
    _admin: AdminUser,
    q: str = Query("", max_length=200),
    role: str | None = Query(None, pattern="^(user|admin)$"),
    active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    filters = []
    if q.strip():
        term = f"%{q.strip().casefold()}%"
        filters.append(
            or_(func.lower(User.email).like(term), func.lower(User.display_name).like(term))
        )
    if role:
        filters.append(User.role == role)
    if active is not None:
        filters.append(User.is_active.is_(active))

    total = db.scalar(select(func.count(User.id)).where(*filters)) or 0
    turtle_count = (
        select(func.count(Turtle.id)).where(Turtle.user_id == User.id).correlate(User).scalar_subquery()
    )
    conversation_count = (
        select(func.count(Conversation.id))
        .where(Conversation.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    message_count = (
        select(func.count(Message.id)).where(Message.user_id == User.id).correlate(User).scalar_subquery()
    )
    ai_request_count = (
        select(func.count(AIUsageLog.id))
        .where(AIUsageLog.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    rows = db.execute(
        select(User, turtle_count, conversation_count, message_count, ai_request_count)
        .where(*filters)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        AdminUserItem(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            turtle_count=turtles or 0,
            conversation_count=conversations or 0,
            message_count=messages or 0,
            ai_request_count=requests or 0,
        )
        for user, turtles, conversations, messages, requests in rows
    ]
    return AdminUserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}", response_model=AdminUserItem)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    db: DB,
    admin: AdminUser,
    _csrf: CSRFSession,
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="找不到使用者。")
    data = payload.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=422, detail="沒有可更新的欄位。")
    if target.id == admin.id:
        raise HTTPException(status_code=409, detail="不能在後台停用或變更自己的管理員權限。")
    if target.role == "admin" and (
        data.get("role") == "user" or data.get("is_active") is False
    ):
        active_admins = db.scalar(
            select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True))
        ) or 0
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="系統至少必須保留一位啟用中的管理員。")

    before = {"role": target.role, "is_active": target.is_active}
    if "role" in data:
        target.role = data["role"]
    if "is_active" in data:
        target.is_active = data["is_active"]
        if not target.is_active:
            db.execute(delete(SessionRecord).where(SessionRecord.user_id == target.id))
    save_audit(db, admin, "user.update", "user", target.id, {"before": before, "after": data})
    db.commit()
    db.refresh(target)
    return AdminUserItem(
        id=target.id,
        email=target.email,
        display_name=target.display_name,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
        last_login_at=target.last_login_at,
        turtle_count=db.scalar(select(func.count(Turtle.id)).where(Turtle.user_id == target.id)) or 0,
        conversation_count=db.scalar(
            select(func.count(Conversation.id)).where(Conversation.user_id == target.id)
        ) or 0,
        message_count=db.scalar(select(func.count(Message.id)).where(Message.user_id == target.id)) or 0,
        ai_request_count=db.scalar(
            select(func.count(AIUsageLog.id)).where(AIUsageLog.user_id == target.id)
        ) or 0,
    )


@router.get("/usage", response_model=AdminUsageListResponse)
def list_usage(
    db: DB,
    _admin: AdminUser,
    status: str | None = Query(None, pattern="^(success|error)$"),
    feature: str | None = Query(None, max_length=30),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    filters = []
    if status:
        filters.append(AIUsageLog.status == status)
    if feature:
        filters.append(AIUsageLog.feature == feature)
    total = db.scalar(select(func.count(AIUsageLog.id)).where(*filters)) or 0
    rows = db.execute(
        select(AIUsageLog, User.email)
        .outerjoin(User, User.id == AIUsageLog.user_id)
        .where(*filters)
        .order_by(AIUsageLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AdminUsageListResponse(
        items=[
            AdminUsageItem(
                id=log.id,
                request_id=log.request_id,
                user_id=log.user_id,
                user_email=email,
                feature=log.feature,
                provider=log.provider,
                model=log.model,
                input_tokens=log.input_tokens,
                output_tokens=log.output_tokens,
                usage_estimated=log.usage_estimated,
                estimated_cost=log.estimated_cost,
                latency_ms=log.latency_ms,
                status=log.status,
                error_code=log.error_code,
                created_at=log.created_at,
            )
            for log, email in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/knowledge", response_model=AdminKnowledgeStatusResponse)
def knowledge_status(db: DB, _admin: AdminUser):
    settings = get_settings()
    signature = embedding_signature(settings.ai_embedding_model)
    rows = db.execute(
        select(
            KnowledgeDocument,
            func.count(KnowledgeChunk.id),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (KnowledgeChunk.embedding.is_not(None))
                            & (KnowledgeChunk.embedding_model == signature),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .outerjoin(KnowledgeChunk)
        .group_by(KnowledgeDocument.id)
        .order_by(KnowledgeDocument.title)
    ).all()
    items = [
        AdminKnowledgeItem(
            id=document.id,
            slug=document.slug,
            title=document.title,
            is_active=document.is_active,
            reviewed_at=document.reviewed_at,
            chunk_count=chunk_count or 0,
            embedded_chunks=embedded or 0,
            updated_at=document.updated_at,
        )
        for document, chunk_count, embedded in rows
    ]
    return AdminKnowledgeStatusResponse(
        items=items,
        documents=len(items),
        active_documents=sum(1 for item in items if item.is_active),
        chunks=sum(item.chunk_count for item in items),
        embedded_chunks=sum(item.embedded_chunks for item in items),
        embedding_model=settings.ai_embedding_model,
    )


@router.post("/knowledge/sync", response_model=AdminKnowledgeSyncResponse)
async def sync_knowledge(db: DB, admin: AdminUser, _csrf: CSRFSession):
    settings = get_settings()
    if not settings.ai_api_key:
        raise HTTPException(status_code=503, detail="尚未設定 NVIDIA API Key。")
    try:
        documents = seed_knowledge_metadata(db, settings.knowledge_path)
        chunks = await embed_missing_chunks(db, get_provider(settings), settings.ai_embedding_model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.friendly_message) from exc
    save_audit(
        db,
        admin,
        "knowledge.sync",
        "knowledge_base",
        details={"updated_documents": documents, "embedded_chunks": chunks},
    )
    db.commit()
    return AdminKnowledgeSyncResponse(
        updated_documents=documents,
        embedded_chunks=chunks,
        message="知識庫同步完成。",
    )


@router.get("/audit", response_model=AdminAuditListResponse)
def list_audit(db: DB, _admin: AdminUser, limit: int = Query(50, ge=1, le=200)):
    total = db.scalar(select(func.count(AdminAuditLog.id))) or 0
    rows = db.execute(
        select(AdminAuditLog, User.email)
        .outerjoin(User, User.id == AdminAuditLog.actor_user_id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
    ).all()
    return AdminAuditListResponse(
        items=[
            AdminAuditItem(
                id=log.id,
                actor_user_id=log.actor_user_id,
                actor_email=email,
                action=log.action,
                target_type=log.target_type,
                target_id=log.target_id,
                details=log.details or {},
                created_at=log.created_at,
            )
            for log, email in rows
        ],
        total=total,
    )


@router.get("/system", response_model=AdminSystemInfoResponse)
def system_info(_admin: AdminUser):
    settings = get_settings()
    return AdminSystemInfoResponse(
        app_env=settings.app_env,
        database_backend="sqlite" if settings.database_url.startswith("sqlite") else "postgresql",
        session_days=settings.session_days,
        ai_requests_per_minute=settings.ai_requests_per_minute,
        ai_per_user_concurrency=settings.ai_per_user_concurrency,
        ai_global_concurrency=settings.ai_global_concurrency,
        max_input_chars=settings.max_input_chars,
        max_image_bytes=settings.max_image_bytes,
        max_images_per_message=settings.max_images_per_message,
        context_recent_messages=settings.context_recent_messages,
        summary_trigger_messages=settings.summary_trigger_messages,
    )


@router.post("/provider/check", response_model=AdminProviderHealthResponse)
async def provider_check(db: DB, admin: AdminUser, _csrf: CSRFSession):
    settings = get_settings()
    checked_at = datetime.now(timezone.utc)
    if not settings.ai_api_key:
        return AdminProviderHealthResponse(
            reachable=False,
            status="not_configured",
            message="尚未設定 NVIDIA API Key。",
            latency_ms=None,
            chat_model_available=False,
            vision_model_available=False,
            embedding_model_available=False,
            checked_at=checked_at,
        )
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=min(settings.ai_timeout_seconds, 30)) as client:
            response = await client.get(
                f"{settings.ai_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {settings.ai_api_key}", "Accept": "application/json"},
            )
        latency_ms = round((time.perf_counter() - started) * 1000)
        if response.is_error:
            message = "NVIDIA 驗證失敗。" if response.status_code in (401, 403) else "NVIDIA 服務暫時無法使用。"
            result = AdminProviderHealthResponse(
                reachable=False,
                status=f"http_{response.status_code}",
                message=message,
                latency_ms=latency_ms,
                chat_model_available=False,
                vision_model_available=False,
                embedding_model_available=False,
                checked_at=checked_at,
            )
        else:
            model_ids = {item.get("id") for item in response.json().get("data", [])}
            result = AdminProviderHealthResponse(
                reachable=True,
                status="ok",
                message="NVIDIA NIM 連線正常。",
                latency_ms=latency_ms,
                chat_model_available=settings.ai_model in model_ids,
                vision_model_available=settings.ai_vision_model in model_ids,
                embedding_model_available=settings.ai_embedding_model in model_ids,
                checked_at=checked_at,
            )
    except (httpx.HTTPError, ValueError):
        result = AdminProviderHealthResponse(
            reachable=False,
            status="unavailable",
            message="無法連線 NVIDIA NIM，請稍後再試。",
            latency_ms=round((time.perf_counter() - started) * 1000),
            chat_model_available=False,
            vision_model_available=False,
            embedding_model_available=False,
            checked_at=checked_at,
        )
    save_audit(
        db,
        admin,
        "provider.check",
        "nvidia_nim",
        details={"status": result.status, "latency_ms": result.latency_ms},
    )
    db.commit()
    return result
