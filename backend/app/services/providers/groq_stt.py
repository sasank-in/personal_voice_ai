import openai
from openai import AsyncOpenAI

from app.services.providers.base import ProviderError, Transcription
from app.services.providers.openai_common import map_openai_error, response_usage

STAGE = "transcribing"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Whisper uses ISO-639-1 codes and has no Odia, which falls back to auto-detection.
WHISPER_LANGUAGES = {"as", "bn", "en", "gu", "hi", "kn", "ml", "mr", "pa", "ta", "te"}


def whisper_language(language_code: str) -> str | None:
    language = language_code.split("-")[0]
    return language if language in WHISPER_LANGUAGES else None


class GroqSpeechToText:
    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        if not api_key:
            raise ProviderError(
                "provider_not_configured", "The Groq API key is not configured.", stage="configuration"
            )
        self._client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL, timeout=timeout_seconds)
        self._model = model

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        language_code: str = "unknown",
    ) -> Transcription:
        options = {}
        language = whisper_language(language_code)
        if language:
            options["language"] = language

        try:
            response = await self._client.audio.transcriptions.create(
                model=self._model,
                file=(filename, audio_bytes),
                **options,
            )
        except openai.APIError as exc:
            raise map_openai_error(
                exc, STAGE, "speech service", "transcription_failed", "We could not transcribe that recording."
            ) from exc

        usage = response_usage(response)
        transcript = (response.text or "").strip()
        if not transcript:
            raise ProviderError(
                "empty_transcript", "No speech was detected in that recording.", stage=STAGE, request_id=usage.request_id
            )
        return Transcription(transcript, usage)
