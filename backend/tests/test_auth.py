import uuid

from app.core.security import create_session_token, read_session_token, verify_password


def test_session_token_round_trip():
    user_id = uuid.uuid4()
    claims = read_session_token(create_session_token(user_id, 3, "secret", 1), "secret")
    assert (claims.user_id, claims.version) == (user_id, 3)


def test_session_token_rejects_tampering_wrong_secret_and_expiry():
    user_id = uuid.uuid4()
    token = create_session_token(user_id, 0, "secret", 1)
    assert read_session_token(token, "other") is None
    assert read_session_token(f"{uuid.uuid4()}{token[36:]}", "secret") is None
    assert read_session_token("garbage", "secret") is None
    assert read_session_token("a.b.c.é", "secret") is None
    assert read_session_token(create_session_token(user_id, 0, "secret", -1), "secret") is None


async def test_crafted_non_ascii_cookie_is_a_401_not_a_crash(users, anonymous_client):
    response = await anonymous_client.get(
        "/api/v1/me", headers={"Cookie": "voice_ai_session=a.b.c.\xe9".encode("latin-1")}
    )
    assert response.status_code == 401


async def test_logout_revokes_a_copied_cookie(client):
    cookie = client.cookies["voice_ai_session"]
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    client.cookies.clear()
    client.cookies.set("voice_ai_session", cookie)
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_password_change_ends_other_sessions_and_keeps_this_one(client, anonymous_client):
    login = {"email": "owner@example.com", "password": "correct-horse"}
    await anonymous_client.post("/api/v1/auth/login", json=login)
    assert (await anonymous_client.get("/api/v1/me")).status_code == 200

    wrong = await client.post(
        "/api/v1/me/password", json={"current_password": "nope", "new_password": "a-new-password"}
    )
    assert wrong.status_code == 400
    short = await client.post(
        "/api/v1/me/password", json={"current_password": "correct-horse", "new_password": "short"}
    )
    assert short.status_code == 422

    changed = await client.post(
        "/api/v1/me/password", json={"current_password": "correct-horse", "new_password": "a-new-password"}
    )
    assert changed.status_code == 204
    assert (await client.get("/api/v1/me")).status_code == 200
    assert (await anonymous_client.get("/api/v1/me")).status_code == 401
    assert (await anonymous_client.post("/api/v1/auth/login", json=login)).status_code == 401
    login["password"] = "a-new-password"
    assert (await anonymous_client.post("/api/v1/auth/login", json=login)).status_code == 200


async def test_login_ignores_email_case_and_treats_unknown_users_alike(users, anonymous_client):
    good = await anonymous_client.post(
        "/api/v1/auth/login", json={"email": " Owner@Example.COM ", "password": "correct-horse"}
    )
    assert good.status_code == 200
    anonymous_client.cookies.clear()
    wrong = await anonymous_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
    )
    unknown = await anonymous_client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_unknown_user_still_does_the_password_work():
    assert verify_password("anything", None) is False
    assert verify_password("not-a-real-password", None) is False


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
