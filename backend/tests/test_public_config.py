def test_public_config_is_available_without_login(client):
    response = client.get("/api/v1/public/config")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"]
    assert data["assistant_name"]
    assert data["ai_provider"] == "nvidia-nim"
    assert isinstance(data["enable_turtle_module"], bool)
    assert "ai_api_key" not in data
