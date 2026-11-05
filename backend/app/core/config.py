import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

REPO_ROOT = Path(__file__).resolve().parents[3]

LLM_DEFAULTS = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "xai": ("https://api.x.ai/v1", "grok-4.7"),
}

MIN_SESSION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = "development"
    app_name: str = "Personal Voice AI"
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str | None = None
    db_name: str = "voice_ai"
    session_secret: str | None = None
    session_days: int = 14
    signup_enabled: bool = True

    seed_user_email: str = "me@example.com"
    seed_user_password: str | None = None

    sarvam_api_key: str | None = None
    sarvam_stt_model: str = "saaras:v4"

    stt_provider: Literal["sarvam", "groq"] = "sarvam"
    groq_stt_model: str = "whisper-large-v3-turbo"

    groq_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GROQ_API_KEY", "Groq-API_Key")
    )
    xai_api_key: str | None = Field(default=None, validation_alias="XAI_API_KEY")

    llm_provider: Literal["groq", "xai"] = "groq"
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_base_url: str | None = None
    llm_model: str | None = None

    login_attempts_per_minute: int = 10
    enrollments_per_hour: int = 5
    turns_per_minute: int = 30

    provider_timeout_seconds: float = 60.0
    max_audio_upload_mb: int = 20
    max_utterance_seconds: int = 29
    max_sample_seconds: int = 60
    audio_storage_dir: str = "storage"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    llm_max_output_tokens: int = 2048

    @model_validator(mode="after")
    def _require_strong_session_secret(self) -> "Settings":
        if self.session_secret and len(self.session_secret) >= MIN_SESSION_SECRET_LENGTH:
            return self
        if self.is_production:
            raise ValueError(f"SESSION_SECRET must be at least {MIN_SESSION_SECRET_LENGTH} characters in production.")
        # Never a known default: without a secret, sessions simply end when the server restarts.
        self.session_secret = secrets.token_hex(32)
        return self

    @property
    def sqlalchemy_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        # URL.create escapes special characters in the password.
        return URL.create(
            "postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def resolved_llm_key(self) -> str | None:
        # Only ever the selected provider's own key, so a key cannot reach the wrong company.
        return self.llm_api_key or (self.groq_api_key if self.llm_provider == "groq" else self.xai_api_key)

    @property
    def resolved_stt_model(self) -> str:
        return self.groq_stt_model if self.stt_provider == "groq" else self.sarvam_stt_model

    @property
    def resolved_llm_base_url(self) -> str:
        return self.llm_base_url or LLM_DEFAULTS[self.llm_provider][0]

    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model or LLM_DEFAULTS[self.llm_provider][1]

    @property
    def storage_path(self) -> Path:
        path = Path(self.audio_storage_dir)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
