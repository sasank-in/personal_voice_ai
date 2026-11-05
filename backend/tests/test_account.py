from sqlalchemy import func, select

from app.models import AudioAsset, Conversation, Message, ProviderRequest, User, UserSession, VoiceProfile
from app.services.providers.base import ProviderError


def delete_account(client, password="correct-horse"):
    return client.request("DELETE", "/api/v1/me", json={"password": password})


async def count(session_factory, model, **filters):
    async with session_factory() as session:
        query = select(func.count()).select_from(model)
        for name, value in filters.items():
            query = query.where(getattr(model, name) == value)
        return await session.scalar(query)


async def test_account_deletion_removes_everything_and_the_cloned_voice(
    client, other_client, conversation, profile, providers, session_factory, storage
):
    await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "Hello", "voice_profile_id": profile["id"]},
    )
    other_conversation = (await other_client.post("/api/v1/conversations", json={})).json()
    await other_client.post(f"/api/v1/conversations/{other_conversation['id']}/messages", json={"content": "Hi"})
    assert list(storage.rglob("*.wav"))

    response = await delete_account(client)
    assert response.status_code == 204
    assert providers.deleted == ["svc-1"]
    assert list(storage.rglob("*.wav")) == []
    assert (await client.get("/api/v1/me")).status_code == 401

    async with session_factory() as session:
        owner = await session.scalar(select(User).where(User.email == "owner@example.com"))
    assert owner is None
    for model in (VoiceProfile, AudioAsset, UserSession):
        # Only the other user's rows remain.
        async with session_factory() as session:
            owners = set(await session.scalars(select(model.user_id)))
        assert len(owners) <= 1
    assert await count(session_factory, Conversation) == 1
    assert await count(session_factory, Message) == 2
    assert (await other_client.get("/api/v1/me")).status_code == 200
    assert (await other_client.get(f"/api/v1/conversations/{other_conversation['id']}/messages")).status_code == 200


async def test_account_deletion_needs_the_password(client, providers):
    response = await delete_account(client, "wrong-password")
    assert response.status_code == 400
    assert (await client.get("/api/v1/me")).status_code == 200


async def test_provider_failure_keeps_the_account_so_deletion_can_be_retried(client, profile, providers, session_factory):
    providers.delete_error = ProviderError("provider_unavailable", "Down.", stage="deleting_voice", retryable=True)
    assert (await delete_account(client)).status_code == 503
    assert (await client.get("/api/v1/me")).status_code == 200

    providers.delete_error = None
    assert (await delete_account(client)).status_code == 204
    assert providers.deleted == ["svc-1"]
    assert await count(session_factory, ProviderRequest) == 0


async def test_deleted_email_can_sign_up_again(client, anonymous_client):
    assert (await delete_account(client)).status_code == 204
    response = await anonymous_client.post(
        "/api/v1/auth/signup", json={"email": "owner@example.com", "password": "a-fresh-password"}
    )
    assert response.status_code == 201
