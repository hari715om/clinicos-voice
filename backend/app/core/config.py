"""
Application configuration via Pydantic Settings.
All values are loaded from environment variables or the .env file.
Import the `settings` singleton — do not instantiate Settings directly.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for ClinicOS Voice."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "ClinicOS Voice"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://clinicos:secret@localhost:5432/clinicos_voice"
    DATABASE_URL_SYNC: Optional[str] = None  # Used by Alembic; falls back to sync transform

    # ── Redis ──────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False

    # ── LiveKit ────────────────────────────────────────────────────────────────
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""

    # ── Groq LLM ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_API_KEYS: str = ""  # comma-separated list of keys for rotation; falls back to GROQ_API_KEY
    GROQ_MODEL: str = "llama-3.1-8b-instant"  # 20k TPM (vs 12k for 70b) — fast, cost-free

    def groq_keys(self) -> list[str]:
        """Return all available Groq API keys for rotation."""
        keys = [k.strip() for k in self.GROQ_API_KEYS.split(",") if k.strip()]
        if not keys and self.GROQ_API_KEY:
            keys = [self.GROQ_API_KEY]
        return keys

    # ── Security ───────────────────────────────────────────────────────────────
    ADMIN_API_KEY: str = "change-me-before-deploy"

    # ── STT / TTS API Keys ─────────────────────────────────────────────────────
    DEEPGRAM_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""

    # ── Clinic (populated post-seed) ───────────────────────────────────────────
    CLINIC_ID: str = ""

    # ── Slot Management ────────────────────────────────────────────────────────
    SLOT_GENERATION_DAYS: int = 30
    SLOT_HOLD_SECONDS: int = 300
    MIN_RESCHEDULE_HOURS: int = 24
    ADVANCE_BOOKING_DAYS: int = 30

    # ── CORS ───────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @field_validator("DATABASE_URL_SYNC", mode="before")
    @classmethod
    def derive_sync_url(cls, v: Optional[str], info: object) -> str:
        """If DATABASE_URL_SYNC is not set, derive it from DATABASE_URL."""
        if v:
            return v
        # Access the raw data through info.data
        try:
            async_url: str = info.data.get("DATABASE_URL", "")
            return async_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
        except Exception:
            return ""


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()


settings: Settings = get_settings()
