from collections import defaultdict, deque
from datetime import datetime
import time

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from ..config import get_settings
from ..dependencies import CSRFSession, CurrentSession, CurrentUser, DB
from ..models import User, utcnow
from ..schemas import APIMessage, AuthResponse, LoginRequest, RegisterRequest, UserResponse
from ..security import (
    clear_auth_cookies,
    create_session,
    create_user,
    normalize_email,
    password_hash,
    set_auth_cookies,
)


router = APIRouter(prefix="/auth", tags=["auth"])
_login_attempts: dict[str, deque[float]] = defaultdict(deque)


def check_login_rate(ip: str) -> None:
    now = time.monotonic()
    attempts = _login_attempts[ip]
    while attempts and now - attempts[0] >= 60:
        attempts.popleft()
    if len(attempts) >= 8:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="登入嘗試過多，請稍後再試。")
    attempts.append(now)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: DB):
    settings = get_settings()
    email = normalize_email(str(payload.email))
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="此 Email 已註冊。")
    user = create_user(db, email, payload.display_name, payload.password)
    token, csrf_token, _ = create_session(db, user, settings)
    set_auth_cookies(response, token, csrf_token, settings)
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: DB):
    settings = get_settings()
    check_login_rate(request.client.host if request.client else "unknown")
    user = db.scalar(select(User).where(User.email == normalize_email(str(payload.email))))
    if not user or not password_hash.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email 或密碼不正確。")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="帳號已停用。")
    user.last_login_at = utcnow()
    db.commit()
    token, csrf_token, _ = create_session(db, user, settings)
    set_auth_cookies(response, token, csrf_token, settings)
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)


@router.get("/me", response_model=AuthResponse)
def me(request: Request, user: CurrentUser):
    settings = get_settings()
    return AuthResponse(
        user=UserResponse.model_validate(user),
        csrf_token=request.cookies.get(settings.csrf_cookie_name, ""),
    )


@router.post("/logout", response_model=APIMessage)
def logout(response: Response, db: DB, session: CSRFSession):
    settings = get_settings()
    db.delete(session)
    db.commit()
    clear_auth_cookies(response, settings)
    return APIMessage(message="已安全登出。")

