from dataclasses import dataclass, field
from typing import Protocol


class ProviderError(Exception):
    """A provider failure, normalized so routes never see SDK objects."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str,
        retryable: bool = False,
        status_code: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage
        self.retryable = retryable
        self.status_code = status_code
        self.request_id = request_id


@dataclass(frozen=True)
class ProviderUsage:
    """What the provider reported about a call, for support tickets and cost estimates."""

    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class CreatedVoice:
    provider_voice_id: str
    reference_text: str | None
    usage: ProviderUsage = field(default_factory=ProviderUsage)


@dataclass(frozen=True)
class Transcription:
    text: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)


@dataclass(frozen=True)
class GeneratedText:
    text: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)


@dataclass(frozen=True)
class SynthesizedAudio:
    audio: bytes
    usage: ProviderUsage = field(default_factory=ProviderUsage)


class SpeechToTextProvider(Protocol):
    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        language_code: str = "unknown",
    ) -> Transcription: ...


class VoiceProvider(Protocol):
    async def create_voice(
        self,
        audio_bytes: bytes,
        filename: str,
        name: str,
        language: str,
    ) -> CreatedVoice: ...

    async def find_voice_id(self, name: str) -> str | None: ...

    async def synthesize(self, voice_id: str, text: str, language_code: str) -> SynthesizedAudio: ...

    async def delete_voice(self, voice_id: str) -> None: ...


class LLMProvider(Protocol):
    async def generate(self, system_prompt: str, messages: list[dict[str, str]]) -> GeneratedText: ...
