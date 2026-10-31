import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import select

from app.api.deps import ProvidersDep, SessionDep, SettingsDep, StoreDep, UserDep, read_upload
from app.core.rate_limit import TurnLimit
from app.models import AudioAsset, Conversation, Message, User, VoiceProfile
from app.schemas.api import (
    AudioErrorOut,
    AudioOut,
    ConversationCreate,
    ConversationOut,
    GenerateAudioRequest,
    MessageCreate,
    MessageOut,
    TurnOut,
)
from app.services import conversation_service, voice_service
from app.services.conversation_service import ConversationEngine, TurnResult

router = APIRouter(prefix="/conversations", tags=["conversations"])


def audio_out(asset: AudioAsset) -> AudioOut:
    return AudioOut(id=asset.id, url=f"/api/v1/audio/{asset.id}", content_type=asset.content_type)


def message_out(message: Message, asset: AudioAsset | None = None) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        audio=audio_out(asset) if asset else None,
    )


def turn_out(result: TurnResult) -> TurnOut:
    error = result.audio_error
    return TurnOut(
        user_message=message_out(result.user_message),
        assistant_message=message_out(result.assistant_message, result.audio),
        audio=audio_out(result.audio) if result.audio else None,
        audio_error=AudioErrorOut(
            code=error.code, message=error.message, stage=error.stage, retryable=error.retryable
        )
        if error
        else None,
    )


async def optional_profile(
    session: SessionDep, user: User, profile_id: uuid.UUID | None
) -> VoiceProfile | None:
    if profile_id is None:
        return None
    return await voice_service.get_ready_profile(session, user, profile_id)


def build_engine(
    session: SessionDep, settings: SettingsDep, store: StoreDep, providers: ProvidersDep
) -> ConversationEngine:
    return ConversationEngine(session, settings, store, providers.llm, providers.stt, providers.voice)


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(body: ConversationCreate, user: UserDep, session: SessionDep) -> Conversation:
    return await conversation_service.create_conversation(session, user, body.title)


@router.get("", response_model=list[ConversationOut])
async def list_conversations(user: UserDep, session: SessionDep) -> list[Conversation]:
    return await conversation_service.list_conversations(session, user)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID, user: UserDep, session: SessionDep, store: StoreDep
) -> None:
    await conversation_service.delete_conversation(session, store, user, conversation_id)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(conversation_id: uuid.UUID, user: UserDep, session: SessionDep) -> list[MessageOut]:
    conversation = await conversation_service.get_conversation(session, user, conversation_id)
    messages = await conversation_service.list_messages(session, conversation)
    audio_ids = [m.audio_asset_id for m in messages if m.audio_asset_id]
    assets = {}
    if audio_ids:
        result = await session.scalars(select(AudioAsset).where(AudioAsset.id.in_(audio_ids)))
        assets = {asset.id: asset for asset in result}
    return [message_out(m, assets.get(m.audio_asset_id)) for m in messages]


@router.post("/{conversation_id}/messages", response_model=TurnOut, dependencies=[TurnLimit])
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    providers: ProvidersDep,
) -> TurnOut:
    conversation = await conversation_service.get_conversation(session, user, conversation_id)
    profile_id = body.voice_profile_id if body.generate_audio else None
    profile = await optional_profile(session, user, profile_id)
    engine = build_engine(session, settings, store, providers)
    return turn_out(await engine.send_text(user, conversation, body.content, profile))


@router.post("/{conversation_id}/audio", response_model=TurnOut, dependencies=[TurnLimit])
async def send_audio(
    conversation_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    providers: ProvidersDep,
    voice_profile_id: Annotated[uuid.UUID | None, Form()] = None,
) -> TurnOut:
    conversation = await conversation_service.get_conversation(session, user, conversation_id)
    profile = await optional_profile(session, user, voice_profile_id)
    audio_bytes = await read_upload(file, settings)
    engine = build_engine(session, settings, store, providers)
    return turn_out(await engine.send_audio(user, conversation, audio_bytes, profile))


@router.post("/{conversation_id}/messages/{message_id}/audio", response_model=AudioOut, dependencies=[TurnLimit])
async def retry_message_audio(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    body: GenerateAudioRequest,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    providers: ProvidersDep,
) -> AudioOut:
    conversation = await conversation_service.get_conversation(session, user, conversation_id)
    profile = await voice_service.get_ready_profile(session, user, body.voice_profile_id)
    engine = build_engine(session, settings, store, providers)
    return audio_out(await engine.generate_message_audio(user, conversation, message_id, profile))
