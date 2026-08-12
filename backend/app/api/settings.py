from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..dependencies import CSRFSession, CurrentUser, DB
from ..models import Turtle, UserSettings
from ..schemas import UserSettingsResponse, UserSettingsUpdate


router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=UserSettingsResponse)
def get_user_settings(db: DB, user: CurrentUser):
    settings = db.get(UserSettings, user.id)
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.patch("/settings", response_model=UserSettingsResponse)
def update_user_settings(payload: UserSettingsUpdate, db: DB, user: CurrentUser, _csrf: CSRFSession):
    settings = db.get(UserSettings, user.id)
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
    data = payload.model_dump(exclude_unset=True)
    if "default_turtle_id" in data and data["default_turtle_id"] is not None:
        if not db.scalar(
            select(Turtle.id).where(Turtle.id == data["default_turtle_id"], Turtle.user_id == user.id)
        ):
            raise HTTPException(status_code=404, detail="找不到指定的預設烏龜。")
    for key, value in data.items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings

