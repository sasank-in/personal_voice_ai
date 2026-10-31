import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import app, create_app
from app.services.providers.sarvam_common import map_error
from sarvamai.core.api_error import ApiError
from tests.conftest import make_wav


async def test_errors_use_one_format_on_unknown_routes(anonymous_client):
    response = await anonymous_client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    wrong_method = await anonymous_client.put("/api/v1/languages")
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"


async def test_unexpected_errors_are_formatted_and_reveal_nothing(client, conversation, providers):
    async def explode(*_):
        raise RuntimeError("secret internal detail")

    providers.generate = explode
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", cookies=client.cookies) as http:
        response = await http.post(f"/api/v1/conversations/{conversation['id']}/messages", json={"content": "Hi"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret" not in response.text


async def test_security_headers_are_set(anonymous_client):
    headers = (await anonymous_client.get("/api/v1/languages")).headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"


async def test_foreign_origin_cannot_change_state(client):
    headers = {"Origin": "http://localhost:9999"}
    response = await client.post("/api/v1/conversations", json={}, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"
    assert "x-frame-options" in response.headers

    allowed = await client.post("/api/v1/conversations", json={}, headers={"Origin": "http://localhost:5173"})
    assert allowed.status_code == 201
    assert (await client.get("/api/v1/me", headers=headers)).status_code == 200


async def test_oversized_bodies_are_refused_before_parsing(anonymous_client):
    too_big = str(get_settings().max_audio_upload_mb * 1024 * 1024 + 2 * 1024 * 1024)
    upload = await anonymous_client.post(
        "/api/v1/voices",
        content=b"x",
        headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": too_big},
    )
    assert upload.status_code == 413

    json_body = await anonymous_client.post(
        "/api/v1/auth/login",
        content=b"x",
        headers={"Content-Type": "application/json", "Content-Length": str(2 * 1024 * 1024)},
    )
    assert json_body.status_code == 413


async def test_chunked_uploads_without_a_length_are_refused(anonymous_client):
    async def body():
        yield b"x"

    response = await anonymous_client.post(
        "/api/v1/voices", content=body(), headers={"Content-Type": "multipart/form-data; boundary=x"}
    )
    assert response.status_code == 411


def test_session_secret_is_never_a_known_default():
    first = Settings(_env_file=None, session_secret=None)
    second = Settings(_env_file=None, session_secret="replace_me")
    assert len(first.session_secret) >= 32 and len(second.session_secret) >= 32
    assert first.session_secret != second.session_secret


def test_production_refuses_a_weak_session_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", session_secret="replace_me")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", session_secret=None)


async def test_production_hides_api_docs():
    production = create_app(Settings(_env_file=None, app_env="production", session_secret="x" * 40))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=production), base_url="http://test") as http:
        assert (await http.get("/docs")).status_code == 404
        assert (await http.get("/openapi.json")).status_code == 404


async def test_repeat_audio_request_keeps_one_file_that_deletion_can_remove(
    client, conversation, profile, providers, storage
):
    body = (
        await client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"content": "Hi", "voice_profile_id": profile["id"]},
        )
    ).json()
    path = f"/api/v1/conversations/{conversation['id']}/messages/{body['assistant_message']['id']}/audio"
    repeat = await client.post(path, json={"voice_profile_id": profile["id"]})
    assert repeat.json()["id"] == body["audio"]["id"]
    assert len(list(storage.rglob("*.wav"))) == 1
    assert len(providers.synthesized) == 1

    await client.delete(f"/api/v1/conversations/{conversation['id']}")
    assert list(storage.rglob("*.wav")) == []


async def test_blank_voice_name_is_refused(client, providers):
    response = await client.post(
        "/api/v1/voices",
        data={"name": "   ", "language": "en-IN", "consent_confirmed": "true"},
        files={"file": ("s.wav", make_wav(), "audio/wav")},
    )
    assert response.json()["error"]["code"] == "invalid_name"
    assert providers.created_names == []


def test_voice_missing_at_provider_gets_a_useful_error():
    error = map_error(
        ApiError(status_code=400, body={"error": {"message": "Voice not found."}}),
        "generating_audio",
        "voice_generation_failed",
        "We could not generate speech.",
    )
    assert error.code == "voice_not_found"
