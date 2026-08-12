from io import BytesIO

from PIL import Image

from app.models import AIUsageLog, KnowledgeChunk, KnowledgeDocument, User
from app.security import create_user
from conftest import register


def make_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 60), "green").save(output, format="PNG")
    return output.getvalue()


def test_upload_validation_and_private_access(client):
    csrf = register(client)
    invalid = client.post(
        "/api/v1/attachments",
        files={"file": ("bad.jpg", b"not-an-image", "image/jpeg")},
        headers={"X-CSRF-Token": csrf},
    )
    assert invalid.status_code == 422
    valid = client.post(
        "/api/v1/attachments",
        files={"file": ("habitat.png", make_png(), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert valid.status_code == 201
    attachment_id = valid.json()["id"]
    assert client.get(f"/api/v1/attachments/{attachment_id}").status_code == 200


def test_admin_dashboard_is_aggregate_only(client, db_session):
    csrf = register(client, "admin@example.com", "管理員")
    user = db_session.query(User).filter_by(email="admin@example.com").one()
    user.role = "admin"; db_session.commit()
    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["users"] == 1
    assert "messages" not in body and "content" not in body


def make_admin(client, db_session):
    csrf = register(client, "admin@example.com", "管理員")
    admin = db_session.query(User).filter_by(email="admin@example.com").one()
    admin.role = "admin"
    db_session.commit()
    return admin, csrf


def test_admin_user_management_is_audited_and_self_protected(client, db_session):
    admin, csrf = make_admin(client, db_session)
    member = create_user(db_session, "member@example.com", "飼主", "safe-password-123")

    listing = client.get("/api/v1/admin/users?q=member")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["email"] == "member@example.com"

    no_csrf = client.patch(f"/api/v1/admin/users/{member.id}", json={"role": "admin"})
    assert no_csrf.status_code == 403
    promoted = client.patch(
        f"/api/v1/admin/users/{member.id}",
        json={"role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    self_change = client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"is_active": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert self_change.status_code == 409

    audits = client.get("/api/v1/admin/audit")
    assert audits.status_code == 200
    assert audits.json()["items"][0]["action"] == "user.update"


def test_admin_usage_and_knowledge_never_return_message_content(client, db_session):
    admin, _ = make_admin(client, db_session)
    db_session.add(
        AIUsageLog(
            request_id="admin-usage-test",
            user_id=admin.id,
            feature="chat",
            provider="nvidia-nim",
            model="test-model",
            input_tokens=10,
            output_tokens=5,
            status="success",
        )
    )
    document = KnowledgeDocument(
        slug="admin-kb-test",
        title="管理測試知識",
        description="測試",
        source_url="https://example.com/kb",
        source_name="測試來源",
        reviewed_at="2026-08-12",
        tags=["測試"],
        content_hash="admin-kb-hash",
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        KnowledgeChunk(
            document_id=document.id,
            chunk_index=0,
            section="測試",
            content="這段私人內容不應由後台狀態 API 回傳。",
            embedding=[1.0, 0.0],
            embedding_model="retired-model",
        )
    )
    db_session.commit()

    usage = client.get("/api/v1/admin/usage")
    assert usage.status_code == 200
    assert usage.json()["items"][0]["request_id"] == "admin-usage-test"
    assert "content" not in usage.text

    knowledge = client.get("/api/v1/admin/knowledge")
    assert knowledge.status_code == 200
    assert any(item["slug"] == "admin-kb-test" for item in knowledge.json()["items"])
    assert "私人內容" not in knowledge.text


def test_regular_user_cannot_access_admin_endpoints(client):
    register(client)
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.get("/api/v1/admin/usage").status_code == 403
