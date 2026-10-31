from app.core.config import get_settings
from app.main import app


def use_limits(**limits):
    settings = get_settings().model_copy(update=limits)
    app.dependency_overrides[get_settings] = lambda: settings


async def test_login_attempts_are_limited(users, anonymous_client):
    use_limits(login_attempts_per_minute=2)
    body = {"email": "owner@example.com", "password": "wrong"}
    assert (await anonymous_client.post("/api/v1/auth/login", json=body)).status_code == 401
    assert (await anonymous_client.post("/api/v1/auth/login", json=body)).status_code == 401
    response = await anonymous_client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


async def test_turns_are_limited_per_user(client, other_client, conversation, providers):
    use_limits(turns_per_minute=1)
    path = f"/api/v1/conversations/{conversation['id']}/messages"
    assert (await client.post(path, json={"content": "One"})).status_code == 200
    assert (await client.post(path, json={"content": "Two"})).status_code == 429
    assert len(providers.llm_calls) == 1

    # The limit is per user, so the other user is unaffected.
    own = (await other_client.post("/api/v1/conversations", json={})).json()
    response = await other_client.post(f"/api/v1/conversations/{own['id']}/messages", json={"content": "Hi"})
    assert response.status_code == 200


async def test_enrollment_is_limited(client, providers):
    use_limits(enrollments_per_hour=1)
    form = {"name": "V", "language": "en-IN", "consent_confirmed": "false"}
    files = {"file": ("s.wav", b"x", "audio/wav")}
    assert (await client.post("/api/v1/voices", data=form, files=files)).status_code == 400
    assert (await client.post("/api/v1/voices", data=form, files=files)).status_code == 429
