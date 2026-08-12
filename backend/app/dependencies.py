from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .models import SessionRecord, User
from .security import get_session_record, validate_csrf


DB = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def current_session(request: Request, db: DB, settings: AppSettings) -> SessionRecord:
    record = get_session_record(db, request.cookies.get(settings.session_cookie_name))
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="請先登入。")
    return record


CurrentSession = Annotated[SessionRecord, Depends(current_session)]


def current_user(db: DB, record: CurrentSession) -> User:
    user = db.scalar(select(User).where(User.id == record.user_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="帳號不存在或已停用。")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def csrf_protected(request: Request, record: CurrentSession, settings: AppSettings) -> SessionRecord:
    validate_csrf(request, record, settings)
    return record


CSRFSession = Annotated[SessionRecord, Depends(csrf_protected)]


def admin_user(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理員權限。")
    return user


AdminUser = Annotated[User, Depends(admin_user)]

