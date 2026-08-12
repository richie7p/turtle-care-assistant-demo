import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response, status
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import SessionRecord, User, UserSettings, utcnow


password_hash = PasswordHash.recommended()


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User, settings: Settings) -> tuple[str, str, SessionRecord]:
    raw_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    record = SessionRecord(
        user_id=user.id,
        token_hash=hash_secret(raw_token),
        csrf_hash=hash_secret(csrf_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.session_days),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return raw_token, csrf_token, record


def set_auth_cookies(response: Response, token: str, csrf_token: str, settings: Settings) -> None:
    max_age = settings.session_days * 86400
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def get_session_record(db: Session, raw_token: str | None) -> SessionRecord | None:
    if not raw_token:
        return None
    record = db.scalar(select(SessionRecord).where(SessionRecord.token_hash == hash_secret(raw_token)))
    if not record:
        return None
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        db.delete(record)
        db.commit()
        return None
    record.last_seen_at = utcnow()
    db.commit()
    return record


def validate_csrf(request: Request, record: SessionRecord, settings: Settings) -> None:
    header = request.headers.get("X-CSRF-Token", "")
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    if not header or not cookie or not hmac.compare_digest(header, cookie):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="安全驗證已失效，請重新整理後再試。")
    if not hmac.compare_digest(hash_secret(header), record.csrf_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="安全驗證已失效，請重新登入。")


def create_user(db: Session, email: str, display_name: str, password: str, role: str = "user") -> User:
    user = User(
        email=normalize_email(email),
        display_name=display_name.strip(),
        password_hash=password_hash.hash(password),
        role=role,
    )
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user


def revoke_expired_sessions(db: Session) -> int:
    result = db.execute(delete(SessionRecord).where(SessionRecord.expires_at <= datetime.now(timezone.utc)))
    db.commit()
    return int(result.rowcount or 0)

