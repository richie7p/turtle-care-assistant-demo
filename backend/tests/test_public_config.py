import pytest
from pydantic import ValidationError

from app.config import Settings


def test_public_config_is_available_without_login(client):
    response = client.get("/api/v1/public/config")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"]
    assert data["assistant_name"]
    assert data["ai_provider"] == "nvidia-nim"
    assert isinstance(data["enable_turtle_module"], bool)
    assert "ai_api_key" not in data


def test_production_rejects_placeholder_security_settings():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_origin="http://example.org",
            session_secret="development-only-change-this-secret-now",
        )


def test_production_accepts_real_https_origin_and_long_secret():
    settings = Settings(
        app_env="production",
        app_origin="https://assistant.acme.test",
        session_secret="a-unique-production-secret-with-more-than-32-characters",
    )
    assert settings.is_production is True
    assert settings.allowed_origins == ["https://assistant.acme.test"]
    assert "http://localhost:8000" not in settings.allowed_origins
