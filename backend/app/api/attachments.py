from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from ..config import get_settings
from ..dependencies import CSRFSession, CurrentUser, DB
from ..models import Attachment, Conversation
from ..schemas import AttachmentResponse
from ..services.uploads import delete_attachment_file, save_image_upload


router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    db: DB,
    user: CurrentUser,
    _csrf: CSRFSession,
    file: UploadFile = File(...),
    conversation_id: str | None = None,
):
    if conversation_id and not db.scalar(
        select(Conversation.id).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    ):
        raise HTTPException(status_code=404, detail="找不到指定對話。")
    attachment = await save_image_upload(
        db,
        get_settings(),
        user.id,
        file,
        purpose="message",
        conversation_id=conversation_id,
    )
    return AttachmentResponse.model_validate(attachment).model_copy(
        update={"url": f"/api/v1/attachments/{attachment.id}"}
    )


@router.get("/{attachment_id}")
def get_attachment(attachment_id: str, db: DB, user: CurrentUser):
    attachment = db.scalar(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.user_id == user.id)
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="找不到附件。")
    path = (Path(get_settings().upload_dir) / attachment.storage_key).resolve()
    if Path(get_settings().upload_dir).resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="附件檔案不存在。")
    return FileResponse(path, media_type=attachment.media_type, filename=attachment.original_name)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: str, db: DB, user: CurrentUser, _csrf: CSRFSession):
    attachment = db.scalar(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.user_id == user.id)
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="找不到附件。")
    if attachment.message_id:
        raise HTTPException(status_code=409, detail="已送出的附件不可單獨刪除。")
    delete_attachment_file(get_settings(), attachment)
    db.delete(attachment)
    db.commit()
    return None

