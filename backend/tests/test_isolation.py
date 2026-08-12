from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from conftest import register


def turtle_payload(name: str):
    return {"name": name, "species": "臺灣斑龜", "turtle_type": "aquatic", "has_uvb": True}


def test_user_data_isolation(db_session):
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as user_a, TestClient(app) as user_b:
        csrf_a = register(user_a, "a@example.com", "A")
        csrf_b = register(user_b, "b@example.com", "B")
        turtle_b = user_b.post("/api/v1/turtles", json=turtle_payload("B 的龜"), headers={"X-CSRF-Token": csrf_b}).json()
        conversation_b = user_b.post("/api/v1/conversations", json={"turtle_id": turtle_b["id"]}, headers={"X-CSRF-Token": csrf_b}).json()

        assert user_a.get(f"/api/v1/turtles/{turtle_b['id']}").status_code == 404
        assert user_a.patch(f"/api/v1/turtles/{turtle_b['id']}", json={"name": "偷改"}, headers={"X-CSRF-Token": csrf_a}).status_code == 404
        assert user_a.get(f"/api/v1/conversations/{conversation_b['id']}").status_code == 404
        assert user_a.patch(f"/api/v1/conversations/{conversation_b['id']}", json={"title": "偷改"}, headers={"X-CSRF-Token": csrf_a}).status_code == 404
        assert user_a.get("/api/v1/turtles").json() == []
        assert user_a.get("/api/v1/conversations").json() == []
    app.dependency_overrides.clear()


def test_conversation_crud(client):
    csrf = register(client)
    created = client.post("/api/v1/conversations", json={}, headers={"X-CSRF-Token": csrf})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    renamed = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "UVB 問題"},
        headers={"X-CSRF-Token": csrf},
    )
    assert renamed.json()["title"] == "UVB 問題"
    assert client.get(f"/api/v1/conversations/{conversation_id}").status_code == 200
    assert client.delete(f"/api/v1/conversations/{conversation_id}", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get(f"/api/v1/conversations/{conversation_id}").status_code == 404

