import httpx
import pytest
from sqlalchemy import select

from app.main import app
from app.models import ProviderRequest
from app.services.providers.base import ProviderError
from tests.conftest import make_wav


@pytest.fixture
def rows(session_factory):
    async def load(operation=None):
        async with session_factory() as session:
            query = select(ProviderRequest).order_by(ProviderRequest.created_at)
            if operation:
                query = query.where(ProviderRequest.operation == operation)
            return list(await session.scalars(query))

    return load


async def send(client, conversation, profile=None, content="Hello"):
    return await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": content, "voice_profile_id": profile["id"] if profile else None},
    )


async def test_llm_call_records_request_id_and_tokens(client, conversation, rows):
    await send(client, conversation)
    row = (await rows("generate"))[0]
    assert row.provider_request_id == "req-llm"
    assert (row.input_tokens, row.output_tokens) == (12, 5)
    assert row.status == "ok"
    assert row.latency_ms >= 0
    assert row.model


async def test_transcription_records_request_id_and_audio_length(client, conversation, rows):
    await client.post(
        f"/api/v1/conversations/{conversation['id']}/audio",
        files={"file": ("s.wav", make_wav(2.0), "audio/wav")},
    )
    row = (await rows("transcribe"))[0]
    assert row.provider_request_id == "req-stt"
    assert row.audio_seconds == pytest.approx(2.0, abs=0.1)


async def test_each_speech_chunk_gets_its_own_row(client, conversation, profile, providers, rows):
    providers.reply = " ".join(f"This is sentence number {i}." for i in range(150))
    response = await send(client, conversation, profile)
    assert response.json()["audio"] is not None
    clone_rows = await rows("clone")
    assert len(clone_rows) == len(providers.synthesized) > 1
    assert len({row.provider_request_id for row in clone_rows}) == len(clone_rows)
    assert sum(row.input_characters for row in clone_rows) == sum(len(text) for _, text, _ in providers.synthesized)
    assert all(row.input_characters <= 1000 for row in clone_rows)


async def test_failed_call_keeps_the_request_id_for_a_support_ticket(client, conversation, providers, rows):
    providers.llm_error = ProviderError("provider_unavailable", "Down.", stage="generating_text", retryable=True, request_id="req-failed")
    assert (await send(client, conversation)).status_code == 503
    row = (await rows("generate"))[0]
    assert (row.status, row.provider_request_id) == ("provider_unavailable", "req-failed")


async def test_voice_failure_is_recorded_while_the_text_reply_survives(client, conversation, profile, providers, rows):
    providers.tts_error = ProviderError("voice_generation_failed", "No.", stage="generating_audio", request_id="req-tts-failed")
    body = (await send(client, conversation, profile)).json()
    assert body["assistant_message"]["content"] == "Here is my answer."
    row = (await rows("clone"))[0]
    assert (row.status, row.provider_request_id) == ("voice_generation_failed", "req-tts-failed")


async def test_unexpected_crash_is_not_recorded_as_ok(client, conversation, providers, rows):
    async def explode(*_):
        raise RuntimeError("boom")

    providers.generate = explode
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", cookies=client.cookies) as http:
        assert (await http.post(f"/api/v1/conversations/{conversation['id']}/messages", json={"content": "Hi"})).status_code == 500
    assert (await rows("generate"))[0].status == "unexpected_error"


async def test_enrollment_and_deletion_are_recorded(client, profile, rows):
    created = (await rows("create_voice"))[0]
    assert created.provider_request_id == "req-create"
    assert created.status == "ok"
    assert created.audio_seconds == pytest.approx(8.0, abs=0.1)

    assert (await client.delete(f"/api/v1/voices/{profile['id']}")).status_code == 204
    assert (await rows("delete_voice"))[0].status == "ok"


async def test_timed_out_enrollment_records_both_attempts(client, providers, rows):
    providers.create_error = ProviderError("provider_timeout", "Timed out.", stage="enrolling", retryable=True)
    providers.existing_voice = "svc-recovered"
    await client.post(
        "/api/v1/voices",
        data={"name": "V", "language": "en-IN", "consent_confirmed": "true"},
        files={"file": ("s.wav", make_wav(), "audio/wav")},
    )
    assert (await rows("create_voice"))[0].status == "provider_timeout"
    assert (await rows("find_voice"))[0].status == "ok"


async def test_usage_rows_are_scoped_to_the_acting_user(client, other_client, conversation, rows):
    await send(client, conversation)
    own = (await other_client.post("/api/v1/conversations", json={})).json()
    await send(other_client, own)
    assert len({row.user_id for row in await rows("generate")}) == 2


async def test_usage_rows_never_contain_conversation_text(client, conversation, rows):
    await send(client, conversation, content="my very private question")
    row = (await rows("generate"))[0]
    values = [getattr(row, column.name) for column in ProviderRequest.__table__.columns]
    assert not any("private" in str(value) for value in values)
