"""Run the adapters through the real SDKs against the response formats in the providers' docs."""

import base64
import json

import httpx
import pytest
from openai import AsyncOpenAI
from sarvamai import AsyncSarvamAI

from app.core.config import Settings
from app.services.providers.base import ProviderError
from app.services.providers.factory import build_llm, build_stt
from app.services.providers.groq_stt import GroqSpeechToText, whisper_language
from app.services.providers.llm import OpenAICompatibleLLM
from app.services.providers.sarvam_stt import SarvamSpeechToText
from app.services.providers.sarvam_voice import SarvamVoice


class Recorder:
    def __init__(self, status=200, body=None):
        self.status = status
        self.body = body
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.body is None:
            return httpx.Response(self.status)
        return httpx.Response(self.status, json=self.body)


def http(recorder: Recorder) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(recorder))


def sarvam_voice(recorder: Recorder) -> SarvamVoice:
    voice = SarvamVoice("test-key", 5)
    voice._client = AsyncSarvamAI(api_subscription_key="test-key", httpx_client=http(recorder))
    return voice


def sarvam_stt(recorder: Recorder) -> SarvamSpeechToText:
    stt = SarvamSpeechToText("test-key", "saaras:v4", 5)
    stt._client = AsyncSarvamAI(api_subscription_key="test-key", httpx_client=http(recorder))
    return stt


def openai_client(recorder: Recorder, base_url: str) -> AsyncOpenAI:
    return AsyncOpenAI(api_key="test-key", base_url=base_url, http_client=http(recorder), max_retries=0)


async def test_sarvam_create_voice_parses_response_and_never_retries():
    recorder = Recorder(201, {"status": "success", "data": {"voice_id": "svc-1", "status": "saved", "reference_text": "Hi"}})
    created = await sarvam_voice(recorder).create_voice(b"wav", "sample.wav", "profile-uuid", "en-IN")
    assert (created.provider_voice_id, created.reference_text) == ("svc-1", "Hi")
    request = recorder.requests[0]
    assert (request.method, request.url.path) == ("POST", "/voices/create")
    assert request.headers["api-subscription-key"] == "test-key"
    assert b"profile-uuid" in request.content and b"en-IN" in request.content

    failing = Recorder(503, {"error": {"message": "Down", "code": "x", "request_id": "r"}})
    with pytest.raises(ProviderError) as error:
        await sarvam_voice(failing).create_voice(b"wav", "sample.wav", "n", "en-IN")
    assert error.value.retryable
    assert len(failing.requests) == 1


async def test_sarvam_synthesize_decodes_audio_and_sends_language():
    encoded = base64.b64encode(b"RIFFaudio").decode()
    recorder = Recorder(200, {"audio_b64": encoded, "audio": encoded, "request_id": "r"})
    audio = await sarvam_voice(recorder).synthesize("svc-1", "Hello", "te-IN")
    assert audio == b"RIFFaudio"
    request = recorder.requests[0]
    assert request.url.path == "/voices/clone"
    assert b"svc-1" in request.content and b"te-IN" in request.content


async def test_sarvam_delete_uses_documented_path_and_treats_404_as_deleted():
    recorder = Recorder(204)
    await sarvam_voice(recorder).delete_voice("svc-1")
    assert (recorder.requests[0].method, recorder.requests[0].url.path) == ("DELETE", "/voices/delete/svc-1")

    missing = Recorder(404, {"error": {"message": "No voice", "code": "x", "request_id": "r"}})
    await sarvam_voice(missing).delete_voice("svc-1")


async def test_sarvam_find_voice_matches_exact_name_only():
    voice = {
        "language": "en-IN", "source": "cloned", "created_by": "u",
        "created_at": "2026-10-31T00:00:00Z", "has_preview": False,
    }
    recorder = Recorder(200, {"status": "success", "data": {"total": 3, "voices": [
        {**voice, "id": "svc-similar", "name": "abc-longer", "status": "active"},
        {**voice, "id": "svc-gone", "name": "abc", "status": "deleted"},
        {**voice, "id": "svc-right", "name": "abc", "status": "active"},
    ]}})
    assert await sarvam_voice(recorder).find_voice_id("abc") == "svc-right"
    assert recorder.requests[0].url.params["search"] == "abc"


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (401, {"error": {"message": "Invalid API key", "code": "x", "request_id": "r"}}, "provider_auth_failed"),
        (403, {"error": {"message": "No", "code": "x", "request_id": "r"}}, "provider_auth_failed"),
        (403, {"error": {"message": "TIER_LIMIT_REACHED", "code": "x", "request_id": "r"}}, "voice_limit_reached"),
        (402, {"error": {"message": "Quota", "code": "x", "request_id": "r"}}, "provider_quota_exceeded"),
        (422, {"error": {"message": "Bad audio", "code": "x", "request_id": "r"}}, "voice_sample_rejected"),
    ],
)
async def test_sarvam_errors_map_to_stable_codes(status, body, code):
    with pytest.raises(ProviderError) as error:
        await sarvam_voice(Recorder(status, body)).create_voice(b"wav", "s.wav", "n", "en-IN")
    assert error.value.code == code
    assert "test-key" not in error.value.message


async def test_sarvam_stt_parses_transcript_and_rejects_empty():
    recorder = Recorder(200, {"request_id": "r", "transcript": " Hello there ", "language_code": "en-IN"})
    assert await sarvam_stt(recorder).transcribe(b"wav", "u.wav", "en-IN") == "Hello there"
    assert recorder.requests[0].url.path == "/speech-to-text"
    assert b"saaras:v4" in recorder.requests[0].content

    with pytest.raises(ProviderError) as error:
        await sarvam_stt(Recorder(200, {"request_id": "r", "transcript": "  "})).transcribe(b"wav", "u.wav")
    assert error.value.code == "empty_transcript"


async def test_xai_uses_responses_without_server_side_storage():
    recorder = Recorder(200, {
        "id": "resp", "object": "response", "created_at": 0, "model": "grok-4.7", "status": "completed",
        "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
        "output": [{"type": "message", "id": "m", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": "Hi there", "annotations": []}]}],
    })
    llm = OpenAICompatibleLLM("xai", "test-key", "https://api.x.ai/v1", "grok-4.7", 5)
    llm._client = openai_client(recorder, "https://api.x.ai/v1")
    assert await llm.generate("Be brief.", [{"role": "user", "content": "Hello"}]) == "Hi there"

    request = recorder.requests[0]
    assert str(request.url) == "https://api.x.ai/v1/responses"
    sent = json.loads(request.content)
    assert sent["store"] is False
    assert sent["instructions"] == "Be brief."
    assert sent["input"] == [{"role": "user", "content": "Hello"}]


async def test_groq_llm_uses_chat_completions_and_maps_errors():
    recorder = Recorder(200, {
        "id": "c", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Hello"}}],
    })
    llm = OpenAICompatibleLLM("groq", "test-key", "https://api.groq.com/openai/v1", "m", 5)
    llm._client = openai_client(recorder, "https://api.groq.com/openai/v1")
    assert await llm.generate("Be brief.", [{"role": "user", "content": "Hi"}]) == "Hello"
    assert json.loads(recorder.requests[0].content)["messages"][0]["role"] == "system"

    llm._client = openai_client(Recorder(401, {"error": {"message": "Bad key"}}), "https://api.groq.com/openai/v1")
    with pytest.raises(ProviderError) as error:
        await llm.generate("Be brief.", [])
    assert error.value.code == "provider_auth_failed"


async def test_groq_stt_sends_iso_language_and_parses_text():
    recorder = Recorder(200, {"text": " Hello there "})
    stt = GroqSpeechToText("test-key", "whisper-large-v3-turbo", 5)
    stt._client = openai_client(recorder, "https://api.groq.com/openai/v1")
    assert await stt.transcribe(b"wav", "u.wav", "te-IN") == "Hello there"
    assert recorder.requests[0].url.path.endswith("/audio/transcriptions")
    assert b"te" in recorder.requests[0].content


def test_whisper_language_mapping():
    assert whisper_language("hi-IN") == "hi"
    assert whisper_language("od-IN") is None
    assert whisper_language("unknown") is None


def test_llm_key_never_crosses_providers():
    xai = Settings(_env_file=None, llm_provider="xai", GROQ_API_KEY="groq-key")
    assert xai.resolved_llm_key is None
    with pytest.raises(ProviderError) as error:
        build_llm(xai)
    assert error.value.code == "provider_not_configured"

    both = Settings(_env_file=None, llm_provider="xai", GROQ_API_KEY="groq-key", XAI_API_KEY="xai-key")
    assert both.resolved_llm_key == "xai-key"
    groq = Settings(_env_file=None, llm_provider="groq", GROQ_API_KEY="groq-key", XAI_API_KEY="xai-key")
    assert groq.resolved_llm_key == "groq-key"
    explicit = Settings(_env_file=None, llm_provider="xai", GROQ_API_KEY="groq-key", LLM_API_KEY="chosen")
    assert explicit.resolved_llm_key == "chosen"


def test_stt_provider_selection():
    groq = Settings(_env_file=None, stt_provider="groq", GROQ_API_KEY="k", SARVAM_API_KEY=None)
    assert isinstance(build_stt(groq), GroqSpeechToText)
    sarvam = Settings(_env_file=None, stt_provider="sarvam", sarvam_api_key="k")
    assert isinstance(build_stt(sarvam), SarvamSpeechToText)
