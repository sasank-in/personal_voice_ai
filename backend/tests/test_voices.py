from app.services.providers.base import ProviderError
from tests.conftest import make_wav


def enroll(client, *, consent="true", language="en-IN", audio=None):
    return client.post(
        "/api/v1/voices",
        data={"name": "My Voice", "language": language, "consent_confirmed": consent},
        files={"file": ("sample.webm", audio if audio is not None else make_wav(), "audio/webm")},
    )


async def test_enrollment_hides_provider_voice_id(client, providers):
    response = await enroll(client)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    assert "svc-" not in response.text
    assert providers.created_names == [body["id"]]


async def test_enrollment_requires_consent(client, providers):
    response = await enroll(client, consent="false")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "consent_required"
    assert providers.created_names == []


async def test_enrollment_rejects_bad_samples(client, providers):
    assert (await enroll(client, audio=make_wav(1.0))).json()["error"]["code"] == "sample_too_short"
    assert (await enroll(client, audio=make_wav(70.0))).json()["error"]["code"] == "sample_too_long"
    assert (await enroll(client, audio=b"not audio" * 50)).json()["error"]["code"] == "invalid_audio"
    assert (await enroll(client, language="ur-IN")).json()["error"]["code"] == "unsupported_language"
    assert providers.created_names == []


async def test_failed_enrollment_is_marked_failed_with_clear_error(client, providers):
    providers.create_error = ProviderError(
        "voice_limit_reached", "The saved voice limit has been reached.", stage="enrolling"
    )
    response = await enroll(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "voice_limit_reached"
    assert [p["status"] for p in (await client.get("/api/v1/voices")).json()] == ["failed"]


async def test_timeout_reconciles_with_voice_already_created(client, providers):
    providers.create_error = ProviderError("provider_timeout", "Timed out.", stage="enrolling", retryable=True)
    providers.existing_voice = "svc-recovered"
    response = await enroll(client)
    assert response.status_code == 201
    assert response.json()["status"] == "ready"
    assert len(providers.created_names) == 1


async def test_timeout_without_voice_is_failed_not_retried(client, providers):
    providers.create_error = ProviderError("provider_timeout", "Timed out.", stage="enrolling", retryable=True)
    response = await enroll(client)
    assert response.status_code == 503
    assert len(providers.created_names) == 1


async def test_delete_removes_provider_voice(client, providers, profile):
    response = await client.delete(f"/api/v1/voices/{profile['id']}")
    assert response.status_code == 204
    assert providers.deleted == ["svc-1"]
    assert (await client.get("/api/v1/voices")).json() == []
    assert (await client.get(f"/api/v1/voices/{profile['id']}")).status_code == 404


async def test_provider_delete_failure_keeps_profile_for_retry(client, providers, profile):
    providers.delete_error = ProviderError("provider_unavailable", "Down.", stage="deleting_voice", retryable=True)
    assert (await client.delete(f"/api/v1/voices/{profile['id']}")).status_code == 503
    assert (await client.get(f"/api/v1/voices/{profile['id']}")).json()["status"] == "ready"

    providers.delete_error = None
    assert (await client.delete(f"/api/v1/voices/{profile['id']}")).status_code == 204
    assert providers.deleted == ["svc-1"]


async def test_other_user_cannot_see_or_delete_profile(client, other_client, providers, profile):
    assert (await other_client.get(f"/api/v1/voices/{profile['id']}")).status_code == 404
    assert (await other_client.delete(f"/api/v1/voices/{profile['id']}")).status_code == 404
    assert (await other_client.get("/api/v1/voices")).json() == []
    assert providers.deleted == []
