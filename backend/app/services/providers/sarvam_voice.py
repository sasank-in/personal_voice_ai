import base64

from sarvamai.core.api_error import ApiError

from app.services.providers.base import CreatedVoice
from app.services.providers.sarvam_common import build_client, map_error


class SarvamVoice:
    def __init__(self, api_key: str | None, timeout_seconds: float) -> None:
        self._client = build_client(api_key, timeout_seconds)

    async def create_voice(
        self,
        audio_bytes: bytes,
        filename: str,
        name: str,
        language: str,
    ) -> CreatedVoice:
        try:
            # No automatic retry: a timeout may occur after the voice was created.
            result = await self._client.voice_cloning.create_voice(
                file=(filename, audio_bytes, "audio/wav"),
                name=name,
                language=language,
                request_options={"max_retries": 0},
            )
        except ApiError as exc:
            if exc.status_code == 422:
                error = map_error(
                    exc,
                    "enrolling",
                    "voice_sample_rejected",
                    "That sample could not be used. Please record it again in a quiet room.",
                )
                raise error from exc
            raise map_error(exc, "enrolling", "enrollment_failed", "We could not create the voice.") from exc
        except Exception as exc:
            raise map_error(exc, "enrolling", "enrollment_failed", "We could not create the voice.") from exc

        return CreatedVoice(
            provider_voice_id=result.data.voice_id,
            reference_text=result.data.reference_text,
        )

    async def find_voice_id(self, name: str) -> str | None:
        try:
            result = await self._client.voice_cloning.list_voices(search=name)
        except Exception as exc:
            raise map_error(exc, "enrolling", "enrollment_failed", "We could not check the voice status.") from exc

        for voice in result.data.voices:
            if voice.name == name and voice.status != "deleted":
                return voice.id
        return None

    async def synthesize(self, voice_id: str, text: str, language_code: str) -> bytes:
        try:
            result = await self._client.voice_cloning.convert(
                voice_id=voice_id,
                text=text,
                language_code=language_code,
            )
        except Exception as exc:
            raise map_error(exc, "generating_audio", "voice_generation_failed", "We could not generate speech.") from exc
        return base64.b64decode(result.audio_b64)

    async def delete_voice(self, voice_id: str) -> None:
        try:
            await self._client.voice_cloning.delete_voice(voice_id)
        except ApiError as exc:
            if exc.status_code == 404:
                return
            raise map_error(exc, "deleting_voice", "voice_deletion_failed", "We could not delete the voice.") from exc
        except Exception as exc:
            raise map_error(exc, "deleting_voice", "voice_deletion_failed", "We could not delete the voice.") from exc
