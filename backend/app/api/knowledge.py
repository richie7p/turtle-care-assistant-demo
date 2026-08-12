from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from ..dependencies import CurrentUser, DB
from ..models import KnowledgeChunk, KnowledgeDocument
from ..schemas import KnowledgeDocumentResponse


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KnowledgeDocumentResponse])
def list_knowledge(db: DB, _user: CurrentUser):
    rows = db.execute(
        select(KnowledgeDocument, func.count(KnowledgeChunk.id))
        .outerjoin(KnowledgeChunk)
        .where(KnowledgeDocument.is_active.is_(True))
        .group_by(KnowledgeDocument.id)
        .order_by(KnowledgeDocument.title)
    ).all()
    return [
        KnowledgeDocumentResponse.model_validate(document).model_copy(update={"chunk_count": chunk_count})
        for document, chunk_count in rows
    ]


@router.get("/{document_id}", response_model=KnowledgeDocumentResponse)
def get_knowledge(document_id: str, db: DB, _user: CurrentUser):
    document = db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.is_active.is_(True),
        )
    )
    if not document:
        raise HTTPException(status_code=404, detail="找不到知識文件。")
    chunk_count = db.scalar(select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.document_id == document.id)) or 0
    return KnowledgeDocumentResponse.model_validate(document).model_copy(update={"chunk_count": chunk_count})

