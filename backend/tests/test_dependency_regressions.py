from io import BytesIO

import pytest
from PIL import Image, GifImagePlugin

from conftest import register


def encoded_image(format: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (24, 16), "green").save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize("format,media_type", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_allowed_upload_formats_round_trip(client, format, media_type):
    csrf = register(client)
    response = client.post(
        "/api/v1/attachments",
        files={"file": ("sample", encoded_image(format), media_type)},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201, response.text
    saved = client.get(response.json()["url"])
    assert saved.status_code == 200
    assert saved.headers["content-type"] == media_type
    with Image.open(BytesIO(saved.content)) as image:
        assert image.format == format
        assert image.size == (24, 16)


def test_unsupported_decoder_is_rejected_before_verification(client, monkeypatch):
    csrf = register(client)
    raw = encoded_image("GIF")

    def unexpected_verify(*args, **kwargs):
        pytest.fail("An unsupported image must not reach verification or decoding")

    monkeypatch.setattr(GifImagePlugin.GifImageFile, "verify", unexpected_verify)
    response = client.post(
        "/api/v1/attachments",
        files={"file": ("disguised.png", raw, "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422


def test_private_attachment_ranges_preserve_owner_isolation(client):
    csrf = register(client, "range-owner@example.com")
    upload = client.post(
        "/api/v1/attachments",
        files={"file": ("habitat.png", encoded_image("PNG"), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert upload.status_code == 201
    url = upload.json()["url"]
    full = client.get(url)
    partial = client.get(url, headers={"Range": "bytes=0-7"})
    assert partial.status_code == 206
    assert partial.content == full.content[:8]
    assert partial.headers["content-range"] == f"bytes 0-7/{len(full.content)}"
    assert client.get(url, headers={"Range": "bytes=999999-"}).status_code == 416

    client.cookies.clear()
    assert client.get(url, headers={"Range": "bytes=0-7"}).status_code == 401
    register(client, "range-other@example.com")
    assert client.get(url, headers={"Range": "bytes=0-7"}).status_code == 404
