import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    # The maximum keeps a huge password from tying up the deliberately slow hash.
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        email = email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("must be a valid email address")
        return email


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    language: str


class UserUpdate(BaseModel):
    language: str


class VoiceProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    provider: str
    status: str
    language: str
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class AudioOut(BaseModel):
    id: uuid.UUID
    url: str
    content_type: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    audio: AudioOut | None = None


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    voice_profile_id: uuid.UUID | None = None
    generate_audio: bool = True


class GenerateAudioRequest(BaseModel):
    voice_profile_id: uuid.UUID


class AudioErrorOut(BaseModel):
    code: str
    message: str
    stage: str
    retryable: bool


class TurnOut(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    audio: AudioOut | None
    audio_error: AudioErrorOut | None


class DeletedAudioOut(BaseModel):
    deleted: int
