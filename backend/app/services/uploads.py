from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Attachment


ALLOWED_FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}


async def save_image_upload(
    db: Session,
    settings: Settings,
    user_id: str,
    upload: UploadFile,
    *,
    purpose: str,
    turtle_id: str | None = None,
    conversation_id: str | None = None,
) -> Attachment:
    raw = await upload.read(settings.max_image_bytes + 1)
    if len(raw) > settings.max_image_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="圖片不可超過 5 MB。")
    if not raw:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="圖片內容為空。")

    try:
        image = Image.open(io.BytesIO(raw))
        if image.width * image.height > 40_000_000:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="圖片解析度過高。",
            )
        image.verify()
        image = Image.open(io.BytesIO(raw))
        image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="無法辨識圖片內容。") from exc

    if image.format not in ALLOWED_FORMATS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="僅支援 JPEG、PNG 與 WebP。")
    image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    media_type, extension = ALLOWED_FORMATS[image.format]
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if media_type == "image/png" else "RGB")
    if media_type == "image/jpeg" and image.mode == "RGBA":
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        image = background

    output = io.BytesIO()
    save_format = "JPEG" if media_type == "image/jpeg" else image.format
    save_options = {"quality": 88, "optimize": True} if save_format in ("JPEG", "WEBP") else {"optimize": True}
    image.save(output, format=save_format, **save_options)
    sanitized = output.getvalue()

    storage_dir = Path(settings.upload_dir) / user_id[:2] / user_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"{user_id[:2]}/{user_id}/{uuid.uuid4().hex}{extension}"
    file_path = Path(settings.upload_dir) / storage_key
    file_path.write_bytes(sanitized)

    attachment = Attachment(
        user_id=user_id,
        turtle_id=turtle_id,
        conversation_id=conversation_id,
        purpose=purpose,
        storage_key=storage_key,
        original_name=(upload.filename or "image")[:255],
        media_type=media_type,
        size_bytes=len(sanitized),
        sha256=hashlib.sha256(sanitized).hexdigest(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def delete_attachment_file(settings: Settings, attachment: Attachment) -> None:
    path = (Path(settings.upload_dir) / attachment.storage_key).resolve()
    upload_root = Path(settings.upload_dir).resolve()
    if upload_root in path.parents and path.is_file():
        path.unlink(missing_ok=True)
