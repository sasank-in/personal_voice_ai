import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, not_found
from app.db.base import utc_now
from app.models import AudioAsset, Conversation, Message, User, VoiceProfile
from app.services.audio_store import AudioStore
from app.services.languages import VOICE_LANGUAGES
from app.services.providers.base import (
    LLMProvider,
    ProviderError,
    SpeechToTextProvider,
    SynthesizedAudio,
    VoiceProvider,
)
from app.services.usage import UsageRecorder
from app.utils.audio import (
    merge_wavs,
    normalize_to_wav,
    split_for_tts,
    strip_markdown,
    wav_duration_seconds,
)

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 20
MAX_PARALLEL_TTS = 3
DEFAULT_TITLE = "New conversation"

SYSTEM_PROMPT = """You are a helpful personal voice assistant.

Reply in {language}.

Communication style:
- Speak naturally and clearly.
- Prefer concise answers unless the user asks for detail.
- Use conversational language suitable for spoken responses.
- Avoid unnecessary Markdown, tables, URLs, and long lists in spoken answers.
- If a question is ambiguous, ask one focused clarification.
- Never claim to be the account owner or impersonate another person.
- Do not invent facts or claim to have performed actions that were not performed."""


@dataclass
class TurnResult:
    user_message: Message
    assistant_message: Message
    audio: AudioAsset | None
    audio_error: ProviderError | None


async def create_conversation(session: AsyncSession, user: User, title: str | None) -> Conversation:
    conversation = Conversation(user_id=user.id, title=title or DEFAULT_TITLE)
    session.add(conversation)
    await session.commit()
    return conversation


async def list_conversations(session: AsyncSession, user: User) -> list[Conversation]:
    result = await session.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    )
    return list(result)


async def get_conversation(session: AsyncSession, user: User, conversation_id: uuid.UUID) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if conversation is None:
        raise not_found("Conversation")
    return conversation


async def list_messages(session: AsyncSession, conversation: Conversation) -> list[Message]:
    # A turn's two messages can share a timestamp; "user" sorts before "assistant" when descending.
    result = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.role.desc())
    )
    return list(result)


async def delete_conversation(
    session: AsyncSession, store: AudioStore, user: User, conversation_id: uuid.UUID
) -> None:
    conversation = await get_conversation(session, user, conversation_id)
    audio_ids = [m.audio_asset_id for m in await list_messages(session, conversation) if m.audio_asset_id]
    assets = await session.scalars(select(AudioAsset).where(AudioAsset.id.in_(audio_ids))) if audio_ids else []
    assets = list(assets)
    await session.delete(conversation)
    await session.flush()
    for asset in assets:
        await session.delete(asset)
    await session.commit()
    for asset in assets:
        await store.delete(asset.object_key)


async def get_audio(session: AsyncSession, user: User, audio_id: uuid.UUID) -> AudioAsset:
    asset = await session.scalar(
        select(AudioAsset).where(AudioAsset.id == audio_id, AudioAsset.user_id == user.id)
    )
    if asset is None:
        raise not_found("Audio")
    return asset


async def delete_all_audio(session: AsyncSession, store: AudioStore, user: User) -> int:
    assets = list(await session.scalars(select(AudioAsset).where(AudioAsset.user_id == user.id)))
    asset_ids = [asset.id for asset in assets]
    if asset_ids:
        await session.execute(
            update(Message).where(Message.audio_asset_id.in_(asset_ids)).values(audio_asset_id=None)
        )
    for asset in assets:
        await session.delete(asset)
    await session.commit()
    for asset in assets:
        await store.delete(asset.object_key)
    return len(assets)


class ConversationEngine:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        store: AudioStore,
        llm: Callable[[], LLMProvider],
        stt: Callable[[], SpeechToTextProvider],
        voice: Callable[[], VoiceProvider],
    ) -> None:
        self._session = session
        self._settings = settings
        self._store = store
        self._llm = llm
        self._stt = stt
        self._voice = voice

    async def send_text(
        self,
        user: User,
        conversation: Conversation,
        content: str,
        profile: VoiceProfile | None,
    ) -> TurnResult:
        return await self._run_turn(user, conversation, content, profile)

    async def send_audio(
        self,
        user: User,
        conversation: Conversation,
        audio_bytes: bytes,
        profile: VoiceProfile | None,
    ) -> TurnResult:
        wav = await normalize_to_wav(audio_bytes, max_seconds=self._settings.max_utterance_seconds + 2)
        if wav_duration_seconds(wav) > self._settings.max_utterance_seconds + 1:
            raise AppError(
                400,
                "recording_too_long",
                f"Keep recordings under {self._settings.max_utterance_seconds + 1} seconds.",
                stage="uploading",
            )
        transcription = await self._usage_for(user).track(
            self._settings.stt_provider,
            "transcribe",
            lambda: self._stt().transcribe(wav, "utterance.wav", user.language),
            model=self._settings.resolved_stt_model,
            audio_seconds=wav_duration_seconds(wav),
        )
        return await self._run_turn(user, conversation, transcription.text, profile)

    async def generate_message_audio(
        self, user: User, conversation: Conversation, message_id: uuid.UUID, profile: VoiceProfile
    ) -> AudioAsset:
        message = await self._session.scalar(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation.id,
                Message.role == "assistant",
            )
        )
        if message is None:
            raise not_found("Message")
        # A repeat request must not replace the link and leave an old file nothing can delete.
        if message.audio_asset_id:
            return await get_audio(self._session, user, message.audio_asset_id)
        asset = await self._synthesize(user, message.content, profile)
        message.audio_asset_id = asset.id
        await self._session.commit()
        return asset

    async def _run_turn(
        self,
        user: User,
        conversation: Conversation,
        content: str,
        profile: VoiceProfile | None,
    ) -> TurnResult:
        history = await list_messages(self._session, conversation)
        messages = [{"role": m.role, "content": m.content} for m in history[-HISTORY_MESSAGES:]]
        messages.append({"role": "user", "content": content})

        language = VOICE_LANGUAGES.get(user.language, "English")
        generated = await self._usage_for(user).track(
            self._settings.llm_provider,
            "generate",
            lambda: self._llm().generate(SYSTEM_PROMPT.format(language=language), messages),
            model=self._settings.resolved_llm_model,
        )
        reply = generated.text

        # Saved before synthesis, so a voice failure cannot lose the reply.
        now = utc_now()
        user_message = Message(conversation_id=conversation.id, role="user", content=content, created_at=now)
        assistant_message = Message(conversation_id=conversation.id, role="assistant", content=reply, created_at=now)
        self._session.add_all([user_message, assistant_message])
        conversation.updated_at = now
        if conversation.title == DEFAULT_TITLE:
            conversation.title = content[:80]
        await self._session.commit()

        audio = None
        audio_error = None
        if profile is not None:
            try:
                audio = await self._synthesize(user, reply, profile)
                assistant_message.audio_asset_id = audio.id
                await self._session.commit()
            except ProviderError as exc:
                logger.warning("Voice generation failed: %s", exc.code)
                audio_error = exc

        return TurnResult(user_message, assistant_message, audio, audio_error)

    async def _synthesize(self, user: User, text: str, profile: VoiceProfile) -> AudioAsset:
        spoken = strip_markdown(text)
        chunks = split_for_tts(spoken)
        if not chunks:
            raise ProviderError("nothing_to_speak", "The reply has no speakable text.", stage="generating_audio")

        usage = self._usage_for(user)
        limit = asyncio.Semaphore(MAX_PARALLEL_TTS)
        voice = self._voice()

        async def synthesize_chunk(chunk: str) -> SynthesizedAudio:
            async with limit:
                return await usage.measure(
                    profile.provider,
                    "clone",
                    lambda: voice.synthesize(profile.provider_voice_id, chunk, profile.language),
                    input_characters=len(chunk),
                )

        await usage.release_connection()
        # gather keeps chunk order. Every chunk finishes first, so each provider call gets its row.
        results = await asyncio.gather(*(synthesize_chunk(chunk) for chunk in chunks), return_exceptions=True)
        await usage.flush()
        for result in results:
            if isinstance(result, BaseException):
                raise result
        audio = merge_wavs([result.audio for result in results])

        audio_id = uuid.uuid4()
        object_key = await self._store.save(user.id, audio_id, audio)
        asset = AudioAsset(
            id=audio_id,
            user_id=user.id,
            kind="generated",
            object_key=object_key,
            content_type="audio/wav",
            duration_seconds=wav_duration_seconds(audio),
        )
        self._session.add(asset)
        await self._session.commit()
        return asset

    def _usage_for(self, user: User) -> UsageRecorder:
        return UsageRecorder(self._session, user.id)
