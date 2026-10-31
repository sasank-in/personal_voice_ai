from typing import Annotated

from fastapi import Cookie, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import read_session_token
from app.db.session import get_session
from app.models import User
from app.services.audio_store import AudioStore
from app.services.providers.base import LLMProvider, SpeechToTextProvider, VoiceProvider
from app.services.providers.factory import build_llm, build_stt, build_voice

SESSION_COOKIE = "voice_ai_session"


class Providers:
    """Built on first use, so text chat works without a voice key and vice versa."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def llm(self) -> LLMProvider:
        return build_llm(self._settings)

    def stt(self) -> SpeechToTextProvider:
        return build_stt(self._settings)

    def voice(self) -> VoiceProvider:
        return build_voice(self._settings)


def get_providers(settings: Annotated[Settings, Depends(get_settings)]) -> Providers:
    return Providers(settings)


def get_audio_store(settings: Annotated[Settings, Depends(get_settings)]) -> AudioStore:
    return AudioStore(settings.storage_path)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    claims = read_session_token(token, settings.session_secret) if token else None
    user = await session.get(User, claims.user_id) if claims else None
    if user is None or user.session_version != claims.version:
        raise AppError(401, "not_authenticated", "Please log in.")
    return user


async def read_upload(file: UploadFile, settings: Settings) -> bytes:
    limit = settings.max_audio_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise AppError(
            413, "file_too_large", f"Audio must be under {settings.max_audio_upload_mb} MB.", stage="uploading"
        )
    if not data:
        raise AppError(400, "invalid_audio", "The recording is empty.", stage="uploading")
    return data


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
UserDep = Annotated[User, Depends(get_current_user)]
ProvidersDep = Annotated[Providers, Depends(get_providers)]
StoreDep = Annotated[AudioStore, Depends(get_audio_store)]
