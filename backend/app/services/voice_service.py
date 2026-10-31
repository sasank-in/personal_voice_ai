import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, not_found
from app.db.base import utc_now
from app.models import User, VoiceProfile
from app.services.languages import VOICE_LANGUAGES
from app.services.providers.base import ProviderError, VoiceProvider
from app.utils.audio import normalize_to_wav, wav_duration_seconds

logger = logging.getLogger(__name__)

CONSENT_TEXT_VERSION = "2026-10-31"
MIN_SAMPLE_SECONDS = 5
ENROLLMENT_SAMPLE_RATE = 24000


async def create_profile(
    session: AsyncSession,
    voice: VoiceProvider,
    settings: Settings,
    user: User,
    name: str,
    language: str,
    consent_confirmed: bool,
    audio_bytes: bytes,
) -> VoiceProfile:
    if not consent_confirmed:
        raise AppError(400, "consent_required", "Confirm that you have the right to clone this voice.")
    if language not in VOICE_LANGUAGES:
        raise AppError(400, "unsupported_language", "That language is not supported for voice cloning.")
    name = name.strip()
    if not name:
        raise AppError(400, "invalid_name", "Give the voice profile a name.")

    wav = await normalize_to_wav(audio_bytes, ENROLLMENT_SAMPLE_RATE, settings.max_sample_seconds + 1)
    duration = wav_duration_seconds(wav)
    if duration < MIN_SAMPLE_SECONDS:
        raise AppError(
            400, "sample_too_short", f"Record at least {MIN_SAMPLE_SECONDS} seconds; 10 to 15 is ideal.", stage="uploading"
        )
    if duration > settings.max_sample_seconds:
        raise AppError(
            400, "sample_too_long", f"Keep the sample under {settings.max_sample_seconds} seconds.", stage="uploading"
        )

    profile = VoiceProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        name=name,
        language=language,
        status="pending",
        consent_confirmed_at=utc_now(),
        consent_text_version=CONSENT_TEXT_VERSION,
    )
    session.add(profile)
    await session.commit()

    # The profile UUID is the provider-side name, so a timed-out attempt can be found again.
    provider_name = str(profile.id)
    try:
        created = await voice.create_voice(wav, "sample.wav", provider_name, language)
        profile.provider_voice_id = created.provider_voice_id
        profile.reference_text = created.reference_text
        profile.status = "ready"
    except ProviderError as exc:
        recovered = await _reconcile(voice, provider_name) if exc.retryable else None
        if not recovered:
            profile.status = "failed"
            await session.commit()
            raise
        profile.provider_voice_id = recovered
        profile.status = "ready"

    await session.commit()
    return profile


async def _reconcile(voice: VoiceProvider, provider_name: str) -> str | None:
    try:
        return await voice.find_voice_id(provider_name)
    except ProviderError:
        logger.warning("Could not reconcile enrollment for profile %s", provider_name)
        return None


async def list_profiles(session: AsyncSession, user: User) -> list[VoiceProfile]:
    result = await session.scalars(
        select(VoiceProfile)
        .where(VoiceProfile.user_id == user.id, VoiceProfile.status != "deleted")
        .order_by(VoiceProfile.created_at.desc())
    )
    return list(result)


async def get_profile(session: AsyncSession, user: User, profile_id: uuid.UUID) -> VoiceProfile:
    profile = await session.scalar(
        select(VoiceProfile).where(
            VoiceProfile.id == profile_id,
            VoiceProfile.user_id == user.id,
            VoiceProfile.status != "deleted",
        )
    )
    if profile is None:
        raise not_found("Voice profile")
    return profile


async def get_ready_profile(session: AsyncSession, user: User, profile_id: uuid.UUID) -> VoiceProfile:
    profile = await get_profile(session, user, profile_id)
    if profile.status != "ready" or not profile.provider_voice_id:
        raise AppError(409, "voice_not_ready", "That voice profile is not ready to use.")
    return profile


async def delete_profile(
    session: AsyncSession, voice: VoiceProvider, user: User, profile_id: uuid.UUID
) -> None:
    profile = await get_profile(session, user, profile_id)
    await session.commit()  # Releases the database connection during the provider call.
    # Provider first: if this fails, the local record remains and deletion can be retried.
    if profile.provider_voice_id:
        await voice.delete_voice(profile.provider_voice_id)
    profile.provider_voice_id = None
    profile.reference_text = None
    profile.status = "deleted"
    await session.commit()
