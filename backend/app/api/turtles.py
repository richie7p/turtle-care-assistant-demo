from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select

from ..config import get_settings
from ..dependencies import CSRFSession, CurrentUser, DB
from ..models import Attachment, Conversation, Turtle
from ..schemas import AttachmentResponse, TurtleCreate, TurtleResponse, TurtleUpdate
from ..services.uploads import delete_attachment_file, save_image_upload


router = APIRouter(prefix="/turtles", tags=["turtles"])


def turtle_response(db: DB, turtle: Turtle) -> TurtleResponse:
    photo = db.scalar(
        select(Attachment)
        .where(Attachment.turtle_id == turtle.id, Attachment.user_id == turtle.user_id, Attachment.purpose == "turtle_photo")
        .order_by(Attachment.created_at.desc())
    )
    data = TurtleResponse.model_validate(turtle).model_dump()
    if photo:
        item = AttachmentResponse.model_validate(photo).model_copy(update={"url": f"/api/v1/attachments/{photo.id}"})
        data["photo"] = item
    return TurtleResponse.model_validate(data)


@router.get("", response_model=list[TurtleResponse])
def list_turtles(db: DB, user: CurrentUser):
    turtles = db.scalars(select(Turtle).where(Turtle.user_id == user.id).order_by(Turtle.created_at.desc())).all()
    return [turtle_response(db, turtle) for turtle in turtles]


@router.post("", response_model=TurtleResponse, status_code=status.HTTP_201_CREATED)
def create_turtle(payload: TurtleCreate, db: DB, user: CurrentUser, _csrf: CSRFSession):
    turtle = Turtle(user_id=user.id, **payload.model_dump())
    db.add(turtle)
    db.commit()
    db.refresh(turtle)
    return turtle_response(db, turtle)


@router.get("/{turtle_id}", response_model=TurtleResponse)
def get_turtle(turtle_id: str, db: DB, user: CurrentUser):
    turtle = db.scalar(select(Turtle).where(Turtle.id == turtle_id, Turtle.user_id == user.id))
    if not turtle:
        raise HTTPException(status_code=404, detail="找不到這隻烏龜。")
    return turtle_response(db, turtle)


@router.patch("/{turtle_id}", response_model=TurtleResponse)
def update_turtle(turtle_id: str, payload: TurtleUpdate, db: DB, user: CurrentUser, _csrf: CSRFSession):
    turtle = db.scalar(select(Turtle).where(Turtle.id == turtle_id, Turtle.user_id == user.id))
    if not turtle:
        raise HTTPException(status_code=404, detail="找不到這隻烏龜。")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(turtle, key, value)
    db.commit()
    db.refresh(turtle)
    return turtle_response(db, turtle)


@router.delete("/{turtle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_turtle(turtle_id: str, db: DB, user: CurrentUser, _csrf: CSRFSession):
    turtle = db.scalar(select(Turtle).where(Turtle.id == turtle_id, Turtle.user_id == user.id))
    if not turtle:
        raise HTTPException(status_code=404, detail="找不到這隻烏龜。")
    settings = get_settings()
    attachments = list(db.scalars(select(Attachment).where(Attachment.turtle_id == turtle.id, Attachment.user_id == user.id)))
    for attachment in attachments:
        delete_attachment_file(settings, attachment)
    db.delete(turtle)
    db.commit()
    return None


@router.post("/{turtle_id}/photo", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_turtle_photo(
    turtle_id: str,
    db: DB,
    user: CurrentUser,
    _csrf: CSRFSession,
    file: UploadFile = File(...),
):
    turtle = db.scalar(select(Turtle).where(Turtle.id == turtle_id, Turtle.user_id == user.id))
    if not turtle:
        raise HTTPException(status_code=404, detail="找不到這隻烏龜。")
    old_photos = list(
        db.scalars(
            select(Attachment).where(
                Attachment.turtle_id == turtle.id,
                Attachment.user_id == user.id,
                Attachment.purpose == "turtle_photo",
            )
        )
    )
    settings = get_settings()
    attachment = await save_image_upload(
        db, settings, user.id, file, purpose="turtle_photo", turtle_id=turtle.id
    )
    for old in old_photos:
        delete_attachment_file(settings, old)
        db.delete(old)
    db.commit()
    return AttachmentResponse.model_validate(attachment).model_copy(
        update={"url": f"/api/v1/attachments/{attachment.id}"}
    )

