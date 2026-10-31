import mimetypes

from app.services.providers.base import ProviderError
from app.services.providers.sarvam_common import build_client, map_error


class SarvamSpeechToText:
    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        self._client = build_client(api_key, timeout_seconds)
        self._model = model

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        language_code: str = "unknown",
    ) -> str:
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        try:
            response = await self._client.speech_to_text.transcribe(
                file=(filename, audio_bytes, content_type),
                model=self._model,
                language_code=language_code,
            )
        except Exception as exc:
            raise map_error(
                exc, "transcribing", "transcription_failed", "We could not transcribe that recording."
            ) from exc

        transcript = (response.transcript or "").strip()
        if not transcript:
            raise ProviderError(
                "empty_transcript", "No speech was detected in that recording.", stage="transcribing"
            )
        return transcript
