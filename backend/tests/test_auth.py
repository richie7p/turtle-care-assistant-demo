from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import SessionRecord
from conftest import register


def test_register_login_logout_and_wrong_password(client):
    csrf = register(client)
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "keeper@example.com"

    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401

    wrong = client.post("/api/v1/auth/login", json={"email": "keeper@example.com", "password": "wrong"})
    assert wrong.status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "keeper@example.com", "password": "safe-password-123"},
    )
    assert login.status_code == 200


def test_unauthenticated_and_csrf_access(client):
    assert client.get("/api/v1/turtles").status_code == 401
    register(client)
    response = client.post(
        "/api/v1/turtles",
        json={"name": "斑斑", "species": "臺灣斑龜", "turtle_type": "aquatic"},
    )
    assert response.status_code == 403


def test_session_expiration(client, db_session):
    register(client)
    session = db_session.scalar(select(SessionRecord))
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_production_origin_allowed_and_unknown_origin_rejected(client):
    allowed = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "http://127.0.0.1:8000"},
        json={"email": "production@example.com", "display_name": "Production", "password": "safe-password-123"},
    )
    assert allowed.status_code == 201

    rejected = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "https://evil.example"},
        json={"email": "blocked@example.com", "display_name": "Blocked", "password": "safe-password-123"},
    )
    assert rejected.status_code == 403
