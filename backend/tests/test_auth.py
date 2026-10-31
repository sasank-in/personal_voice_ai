import uuid

from app.core.security import create_session_token, read_session_token


def test_session_token_round_trip():
    user_id = uuid.uuid4()
    assert read_session_token(create_session_token(user_id, "secret", 1), "secret") == user_id


def test_session_token_rejects_tampering_wrong_secret_and_expiry():
    user_id = uuid.uuid4()
    token = create_session_token(user_id, "secret", 1)
    assert read_session_token(token, "other") is None
    assert read_session_token(f"{uuid.uuid4()}{token[36:]}", "secret") is None
    assert read_session_token("garbage", "secret") is None
    assert read_session_token(create_session_token(user_id, "secret", -1), "secret") is None


async def test_protected_routes_require_login(anonymous_client):
    for path in ("/api/v1/me", "/api/v1/voices", "/api/v1/conversations", f"/api/v1/audio/{uuid.uuid4()}"):
        response = await anonymous_client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "not_authenticated"


async def test_wrong_password_is_rejected(users, anonymous_client):
    response = await anonymous_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


async def test_session_cookie_is_http_only(users, anonymous_client):
    response = await anonymous_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "correct-horse"}
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


async def test_language_setting_is_limited_to_voice_languages(client):
    assert (await client.patch("/api/v1/me", json={"language": "te-IN"})).json()["language"] == "te-IN"
    assert (await client.patch("/api/v1/me", json={"language": "ur-IN"})).status_code == 400
