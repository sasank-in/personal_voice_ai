import io
import math
import struct
import wave
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_audio_store, get_providers
from app.core.rate_limit import reset_rate_limits
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import User
from app.services.audio_store import AudioStore
from app.services.providers.base import CreatedVoice, ProviderError

PASSWORD = "correct-horse"


def make_wav(seconds: float = 8.0, rate: int = 24000) -> bytes:
    frames = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / rate)))
        for i in range(int(seconds * rate))
    )
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(frames)
    return output.getvalue()


class FakeProviders:
    def __init__(self) -> None:
        self.reply = "Here is my answer."
        self.transcript = "What is a vector database?"
        self.llm_error: ProviderError | None = None
        self.stt_error: ProviderError | None = None
        self.tts_error: ProviderError | None = None
        self.create_error: ProviderError | None = None
        self.delete_error: ProviderError | None = None
        self.existing_voice: str | None = None
        self.llm_calls: list[tuple[str, list[dict]]] = []
        self.synthesized: list[tuple[str, str, str]] = []
        self.created_names: list[str] = []
        self.deleted: list[str] = []

    def llm(self):
        return self

    def stt(self):
        return self

    def voice(self):
        return self

    async def generate(self, system_prompt, messages):
        self.llm_calls.append((system_prompt, messages))
        if self.llm_error:
            raise self.llm_error
        return self.reply

    async def transcribe(self, audio_bytes, filename, language_code="unknown"):
        if self.stt_error:
            raise self.stt_error
        return self.transcript

    async def create_voice(self, audio_bytes, filename, name, language):
        self.created_names.append(name)
        if self.create_error:
            raise self.create_error
        return CreatedVoice(f"svc-{len(self.created_names)}", "Reference text")

    async def find_voice_id(self, name):
        return self.existing_voice

    async def synthesize(self, voice_id, text, language_code):
        self.synthesized.append((voice_id, text, language_code))
        if self.tts_error:
            raise self.tts_error
        return make_wav(0.1)

    async def delete_voice(self, voice_id):
        if self.delete_error:
            raise self.delete_error
        self.deleted.append(voice_id)


@pytest.fixture
def providers() -> FakeProviders:
    return FakeProviders()


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture
async def users(session_factory):
    async with session_factory() as session:
        password_hash = hash_password(PASSWORD)
        session.add_all(
            [
                User(email="owner@example.com", password_hash=password_hash),
                User(email="other@example.com", password_hash=password_hash),
            ]
        )
        await session.commit()


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture(autouse=True)
def overrides(session_factory, providers, storage):
    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_providers] = lambda: providers
    app.dependency_overrides[get_audio_store] = lambda: AudioStore(storage)
    reset_rate_limits()
    yield
    app.dependency_overrides.clear()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _login(client: httpx.AsyncClient, email: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200


@pytest.fixture
async def client(users):
    async with _client() as http:
        await _login(http, "owner@example.com")
        yield http


@pytest.fixture
async def other_client(users):
    async with _client() as http:
        await _login(http, "other@example.com")
        yield http


@pytest.fixture
async def anonymous_client():
    async with _client() as http:
        yield http


@pytest.fixture
async def profile(client) -> dict:
    response = await client.post(
        "/api/v1/voices",
        data={"name": "My Voice", "language": "en-IN", "consent_confirmed": "true"},
        files={"file": ("sample.wav", make_wav(), "audio/wav")},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def conversation(client) -> dict:
    response = await client.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    return response.json()
