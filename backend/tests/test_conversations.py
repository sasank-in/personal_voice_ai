from app.services.providers.base import ProviderError
from tests.conftest import make_wav


def send(client, conversation, content="Hello", profile=None, generate_audio=True):
    return client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={
            "content": content,
            "voice_profile_id": profile["id"] if profile else None,
            "generate_audio": generate_audio,
        },
    )


def send_audio(client, conversation, profile=None, audio=None):
    return client.post(
        f"/api/v1/conversations/{conversation['id']}/audio",
        data={"voice_profile_id": profile["id"]} if profile else {},
        files={"file": ("speech.webm", audio if audio is not None else make_wav(2.0), "audio/webm")},
    )


async def test_text_turn_returns_playable_audio_and_persists(client, conversation, profile, providers):
    response = await send(client, conversation, "Explain RAG.", profile)
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_message"]["content"] == "Here is my answer."
    assert body["audio_error"] is None

    audio = await client.get(body["audio"]["url"])
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"
    assert audio.content[:4] == b"RIFF"

    history = (await client.get(f"/api/v1/conversations/{conversation['id']}/messages")).json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["audio"]["id"] == body["audio"]["id"]


async def test_text_only_turn_makes_no_voice_call(client, conversation, profile, providers):
    response = await send(client, conversation, profile=profile, generate_audio=False)
    assert response.json()["audio"] is None
    assert providers.synthesized == []


async def test_voice_failure_preserves_text_and_can_be_retried(client, conversation, profile, providers):
    providers.tts_error = ProviderError(
        "voice_generation_failed", "We could not generate speech.", stage="generating_audio", retryable=True
    )
    response = await send(client, conversation, profile=profile)
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_message"]["content"] == "Here is my answer."
    assert body["audio"] is None
    assert body["audio_error"]["code"] == "voice_generation_failed"

    history = (await client.get(f"/api/v1/conversations/{conversation['id']}/messages")).json()
    assert len(history) == 2

    providers.tts_error = None
    message_id = body["assistant_message"]["id"]
    retry = await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/{message_id}/audio",
        json={"voice_profile_id": profile["id"]},
    )
    assert retry.status_code == 200
    history = (await client.get(f"/api/v1/conversations/{conversation['id']}/messages")).json()
    assert history[1]["audio"]["id"] == retry.json()["id"]


async def test_llm_failure_saves_nothing_so_retry_cannot_duplicate(client, conversation, providers):
    providers.llm_error = ProviderError(
        "provider_unavailable", "Down.", stage="generating_text", retryable=True
    )
    response = await send(client, conversation)
    assert response.status_code == 503
    assert response.json()["error"]["stage"] == "generating_text"
    assert (await client.get(f"/api/v1/conversations/{conversation['id']}/messages")).json() == []


async def test_provider_auth_failure_does_not_look_like_a_logout(client, conversation, providers):
    providers.llm_error = ProviderError(
        "provider_auth_failed", "Rejected.", stage="generating_text", status_code=401
    )
    assert (await send(client, conversation)).status_code == 502


async def test_history_and_language_reach_the_llm(client, conversation, providers):
    await client.patch("/api/v1/me", json={"language": "hi-IN"})
    await send(client, conversation, "First")
    await send(client, conversation, "Second")
    system_prompt, messages = providers.llm_calls[-1]
    assert "Reply in Hindi." in system_prompt
    assert [m["content"] for m in messages] == ["First", "Here is my answer.", "Second"]


async def test_title_comes_from_first_message(client, conversation):
    await send(client, conversation, "Tell me about tides")
    await send(client, conversation, "And the moon?")
    titles = [c["title"] for c in (await client.get("/api/v1/conversations")).json()]
    assert titles == ["Tell me about tides"]


async def test_long_replies_are_chunked_and_markdown_stripped(client, conversation, profile, providers):
    providers.reply = "**Intro.** " + " ".join(f"This is sentence {i}." for i in range(150))
    response = await send(client, conversation, profile=profile)
    assert response.status_code == 200
    assert len(providers.synthesized) > 1
    assert all(len(text) <= 1000 for _, text, _ in providers.synthesized)
    assert "**" not in providers.synthesized[0][1]
    assert all(language == "en-IN" for _, _, language in providers.synthesized)


async def test_speech_turn_returns_transcript_reply_and_audio(client, conversation, profile, providers):
    response = await send_audio(client, conversation, profile)
    assert response.status_code == 200
    body = response.json()
    assert body["user_message"]["content"] == "What is a vector database?"
    assert body["assistant_message"]["content"] == "Here is my answer."
    assert body["audio"] is not None


async def test_speech_turn_reports_each_failed_stage(client, conversation, providers):
    assert (await send_audio(client, conversation, audio=b"junk" * 100)).json()["error"]["code"] == "invalid_audio"

    too_long = await send_audio(client, conversation, audio=make_wav(35.0))
    assert too_long.json()["error"]["code"] == "recording_too_long"

    providers.stt_error = ProviderError(
        "empty_transcript", "No speech was detected.", stage="transcribing"
    )
    response = await send_audio(client, conversation)
    assert response.status_code == 422
    assert response.json()["error"]["stage"] == "transcribing"
    assert providers.llm_calls == []


async def test_other_user_cannot_reach_conversation_audio_or_profile(
    client, other_client, conversation, profile, providers
):
    body = (await send(client, conversation, profile=profile)).json()
    path = f"/api/v1/conversations/{conversation['id']}"

    assert (await other_client.get(f"{path}/messages")).status_code == 404
    assert (await other_client.post(f"{path}/messages", json={"content": "Hi"})).status_code == 404
    assert (await other_client.delete(path)).status_code == 404
    assert (await other_client.get(body["audio"]["url"])).status_code == 404

    own = (await other_client.post("/api/v1/conversations", json={})).json()
    response = await send(other_client, own, profile=profile)
    assert response.status_code == 404


async def test_unready_profile_is_refused(client, conversation, providers):
    providers.create_error = ProviderError("enrollment_failed", "No.", stage="enrolling")
    await client.post(
        "/api/v1/voices",
        data={"name": "Bad", "language": "en-IN", "consent_confirmed": "true"},
        files={"file": ("s.wav", make_wav(), "audio/wav")},
    )
    failed = (await client.get("/api/v1/voices")).json()[0]
    response = await send(client, conversation, profile=failed)
    assert response.status_code == 409


async def test_deleting_conversation_removes_its_audio_files(client, conversation, profile, storage):
    body = (await send(client, conversation, profile=profile)).json()
    assert list(storage.rglob("*.wav"))
    assert (await client.delete(f"/api/v1/conversations/{conversation['id']}")).status_code == 204
    assert list(storage.rglob("*.wav")) == []
    assert (await client.get(body["audio"]["url"])).status_code == 404


async def test_deleting_all_audio_keeps_the_text(client, conversation, profile, storage):
    await send(client, conversation, profile=profile)
    response = await client.delete("/api/v1/audio")
    assert response.json() == {"deleted": 1}
    assert list(storage.rglob("*.wav")) == []
    history = (await client.get(f"/api/v1/conversations/{conversation['id']}/messages")).json()
    assert len(history) == 2 and history[1]["audio"] is None
