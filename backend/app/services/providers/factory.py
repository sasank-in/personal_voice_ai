from app.core.config import Settings
from app.services.providers.base import SpeechToTextProvider
from app.services.providers.groq_stt import GroqSpeechToText
from app.services.providers.llm import OpenAICompatibleLLM
from app.services.providers.sarvam_stt import SarvamSpeechToText
from app.services.providers.sarvam_voice import SarvamVoice


def build_stt(settings: Settings) -> SpeechToTextProvider:
    if settings.stt_provider == "groq":
        return GroqSpeechToText(
            settings.groq_api_key, settings.groq_stt_model, settings.provider_timeout_seconds
        )
    return SarvamSpeechToText(
        settings.sarvam_api_key, settings.sarvam_stt_model, settings.provider_timeout_seconds
    )


def build_voice(settings: Settings) -> SarvamVoice:
    return SarvamVoice(settings.sarvam_api_key, settings.provider_timeout_seconds)


def build_llm(settings: Settings) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        settings.llm_provider,
        settings.resolved_llm_key,
        settings.resolved_llm_base_url,
        settings.resolved_llm_model,
        settings.provider_timeout_seconds,
    )
