from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_ENV: str = "production"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: Optional[str] = "redis://localhost:6379"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_BACKEND_URL: str = "redis://localhost:6379/1"

    # AI Providers
    GEMINI_API_KEY: str
    GROQ_API_KEY: str
    DEEPGRAM_API_KEY: str
    PHONAD_LAB_API_KEY: str

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    OPENAI_API_KEY: Optional[str] = None

    @property
    def cloudinary_config(self) -> dict:
        return {
            "cloud_name": self.CLOUDINARY_CLOUD_NAME,
            "api_key": self.CLOUDINARY_API_KEY,
            "api_secret": self.CLOUDINARY_API_SECRET,
        }


settings = Settings()