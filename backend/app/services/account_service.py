import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_session_token
from app.db.base import utc_now
from app.models import (
    AudioAsset,
    Conversation,
    Message,
    ProviderRequest,
    User,
    UserSession,
    VoiceProfile,
)
from app.services.audio_store import AudioStore
from app.services.providers.base import VoiceProvider


def _as_utc(moment: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone-aware columns.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def start_session(session: AsyncSession, user: User, settings: Settings) -> str:
    """Records a new logged-in device and returns its cookie value."""
    now = utc_now()
    existing = await session.scalars(select(UserSession).where(UserSession.user_id == user.id))
    for expired in [row for row in existing if _as_utc(row.expires_at) <= now]:
        await session.delete(expired)

    row = UserSession(id=uuid.uuid4(), user_id=user.id, expires_at=now + timedelta(days=settings.session_days))
    session.add(row)
    await session.commit()
    return create_session_token(row.id, int(row.expires_at.timestamp()), settings.session_secret)


async def end_session(session: AsyncSession, session_id: uuid.UUID) -> None:
    await session.execute(delete(UserSession).where(UserSession.id == session_id))
    await session.commit()


async def end_all_sessions(session: AsyncSession, user_id: uuid.UUID, keep: uuid.UUID | None = None) -> None:
    query = delete(UserSession).where(UserSession.user_id == user_id)
    if keep is not None:
        query = query.where(UserSession.id != keep)
    await session.execute(query)
    await session.commit()


async def delete_account(
    session: AsyncSession,
    voice: VoiceProvider | None,
    store: AudioStore,
    user: User,
) -> None:
    """Deletes the cloned voices at the provider first, then every local trace of the user."""
    profiles = list(
        await session.scalars(
            select(VoiceProfile).where(VoiceProfile.user_id == user.id, VoiceProfile.provider_voice_id.is_not(None))
        )
    )
    for profile in profiles:
        # If this fails, the account stays and deletion can be retried; voices already
        # deleted at the provider are recorded as deleted here.
        await voice.delete_voice(profile.provider_voice_id)
        profile.provider_voice_id = None
        profile.status = "deleted"
        await session.commit()

    user_id = user.id
    conversation_ids = select(Conversation.id).where(Conversation.user_id == user_id)
    # Explicit deletes in dependency order, so this does not rely on database cascades.
    await session.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
    for model in (Conversation, AudioAsset, ProviderRequest, VoiceProfile, UserSession):
        await session.execute(delete(model).where(model.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()
    await store.delete_user_files(user_id)
