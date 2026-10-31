import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import ProvidersDep, SessionDep, SettingsDep, UserDep, read_upload
from app.core.rate_limit import EnrollmentLimit
from app.models import VoiceProfile
from app.schemas.api import VoiceProfileOut
from app.services import voice_service

router = APIRouter(prefix="/voices", tags=["voices"])


@router.post("", response_model=VoiceProfileOut, status_code=201, dependencies=[EnrollmentLimit])
async def create_voice(
    name: Annotated[str, Form(min_length=1, max_length=100)],
    language: Annotated[str, Form()],
    consent_confirmed: Annotated[bool, Form()],
    file: Annotated[UploadFile, File()],
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    providers: ProvidersDep,
) -> VoiceProfile:
    audio_bytes = await read_upload(file, settings)
    return await voice_service.create_profile(
        session, providers.voice(), settings, user, name, language, consent_confirmed, audio_bytes
    )


@router.get("", response_model=list[VoiceProfileOut])
async def list_voices(user: UserDep, session: SessionDep) -> list[VoiceProfile]:
    return await voice_service.list_profiles(session, user)


@router.get("/{profile_id}", response_model=VoiceProfileOut)
async def get_voice(profile_id: uuid.UUID, user: UserDep, session: SessionDep) -> VoiceProfile:
    return await voice_service.get_profile(session, user, profile_id)


@router.delete("/{profile_id}", status_code=204)
async def delete_voice(
    profile_id: uuid.UUID, user: UserDep, session: SessionDep, providers: ProvidersDep
) -> None:
    profile = await voice_service.get_profile(session, user, profile_id)
    voice = providers.voice() if profile.provider_voice_id else None
    await voice_service.delete_profile(session, voice, user, profile_id)
