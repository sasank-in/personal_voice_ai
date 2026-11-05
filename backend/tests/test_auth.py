import time
import uuid

from app.core.config import get_settings
from app.core.security import create_session_token, read_session_token, verify_password
from app.main import app


def future(seconds: int = 3600) -> int:
    return int(time.time()) + seconds


def test_session_token_round_trip():
    session_id = uuid.uuid4()
    claims = read_session_token(create_session_token(session_id, future(), "secret"), "secret")
    assert claims.session_id == session_id


def test_session_token_rejects_tampering_wrong_secret_and_expiry():
    session_id = uuid.uuid4()
    token = create_session_token(session_id, future(), "secret")
    assert read_session_token(token, "other") is None
    assert read_session_token(f"{uuid.uuid4()}{token[36:]}", "secret") is None
    assert read_session_token("garbage", "secret") is None
    assert read_session_token("a.b.é", "secret") is None
    assert read_session_token(create_session_token(session_id, future(-1), "secret"), "secret") is None


def test_unrecognized_stored_hash_is_a_failed_login_not_a_crash():
    assert verify_password("anything", "not-a-real-hash-format") is False


async def test_logout_ends_only_this_device(client, anonymous_client):
    await anonymous_client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "correct-horse"})
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.get("/api/v1/me")).status_code == 401
    assert (await anonymous_client.get("/api/v1/me")).status_code == 200


async def test_logout_everywhere_ends_every_device(client, anonymous_client):
    await anonymous_client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "correct-horse"})
    assert (await client.post("/api/v1/auth/logout-everywhere")).status_code == 204
    assert (await client.get("/api/v1/me")).status_code == 401
    assert (await anonymous_client.get("/api/v1/me")).status_code == 401


async def test_auth_options_report_whether_signup_is_on(anonymous_client):
    assert (await anonymous_client.get("/api/v1/auth/options")).json() == {"signup_enabled": True}
    settings = get_settings().model_copy(update={"signup_enabled": False})
    app.dependency_overrides[get_settings] = lambda: settings
    assert (await anonymous_client.get("/api/v1/auth/options")).json() == {"signup_enabled": False}


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


async def test_signup_creates_user_and_starts_session(anonymous_client):
    response = await anonymous_client.post(
        "/api/v1/auth/signup", json={"email": " New.User@Example.COM ", "password": "a-secure-password"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "new.user@example.com"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert (await anonymous_client.get("/api/v1/me")).json()["email"] == "new.user@example.com"


async def test_signup_rejects_duplicate_email_and_invalid_inputs(users, anonymous_client):
    duplicate = await anonymous_client.post(
        "/api/v1/auth/signup", json={"email": " OWNER@example.com ", "password": "a-secure-password"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_already_registered"

    short_password = await anonymous_client.post(
        "/api/v1/auth/signup", json={"email": "new@example.com", "password": "short"}
    )
    invalid_email = await anonymous_client.post(
        "/api/v1/auth/signup", json={"email": "not-an-email", "password": "a-secure-password"}
    )
    assert short_password.status_code == invalid_email.status_code == 422


async def test_signup_can_be_turned_off(anonymous_client):
    settings = get_settings().model_copy(update={"signup_enabled": False})
    app.dependency_overrides[get_settings] = lambda: settings
    response = await anonymous_client.post(
        "/api/v1/auth/signup", json={"email": "new@example.com", "password": "a-secure-password"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "signup_disabled"


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
