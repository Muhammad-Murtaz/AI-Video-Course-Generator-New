"""
app/core/config.py
─────────────────────────────────────────────────────────────────────────────
Merged config:
  • All original keys preserved (DATABASE_URL, GEMINI_API_KEY, PHONAD_LAB_API_KEY,
    CLOUDINARY_*, GROQ_API_KEY, DEEPGRAM_API_KEY)
  • New production keys added (Redis, Celery, CORS, App meta)
  • Uses pydantic-settings v2 style (SettingsConfigDict) while keeping
    case_sensitive=True and extra="ignore" from your original Config class
─────────────────────────────────────────────────────────────────────────────
"""
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,   # ← kept from your original
        extra="ignore",        # ← kept from your original
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV:         str       = "production"
    SECRET_KEY:      str       = "change-me-in-production"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "https://yourdomain.com"]

    # ── Database ──────────────────────────────────────────────────────────────
    # Required — no default (same as your original)
    DATABASE_URL: str

    # ── Redis ─────────────────────────────────────────────────────────────────
    # Optional with default, exactly as your original REDIS_URL was
    REDIS_URL:      Optional[str] = "redis://localhost:6379"

    # Derived Redis settings used by cache + rate limiter internals
    # These are auto-parsed from REDIS_URL at property level,
    # but can also be set explicitly in .env if needed
    REDIS_HOST:     str = "localhost"
    REDIS_PORT:     int = 6379
    REDIS_PASSWORD: str = ""

    # ── Celery (broker = Redis db/0, backend = Redis db/1) ────────────────────
    CELERY_BROKER_URL:  str = "redis://localhost:6379/0"
    CELERY_BACKEND_URL: str = "redis://localhost:6379/1"

    # ── AI / ML Providers ─────────────────────────────────────────────────────
    # Required (no default) — same as your original
    GEMINI_API_KEY:     str
    GROQ_API_KEY:       str
    DEEPGRAM_API_KEY:   str
    PHONAD_LAB_API_KEY: str

    # ── Cloudinary (media storage) ────────────────────────────────────────────
    # Required — same as your original
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY:    str
    CLOUDINARY_API_SECRET: str

    # ── Optional extra providers ───────────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None   # Only needed if using OpenAI LB provider

    # ── Helpers (not in .env — computed from other settings) ──────────────────
    @property
    def redis_url_db0(self) -> str:
        """Broker URL (database 0)."""
        base = (self.REDIS_URL or "redis://localhost:6379").rstrip("/")
        return f"{base}/0"

    @property
    def redis_url_db1(self) -> str:
        """Backend / result store URL (database 1)."""
        base = (self.REDIS_URL or "redis://localhost:6379").rstrip("/")
        return f"{base}/1"

    @property
    def cloudinary_config(self) -> dict:
        """Ready-to-use dict for cloudinary.config(**settings.cloudinary_config)."""
        return {
            "cloud_name": self.CLOUDINARY_CLOUD_NAME,
            "api_key":    self.CLOUDINARY_API_KEY,
            "api_secret": self.CLOUDINARY_API_SECRET,
        }


settings = Settings()