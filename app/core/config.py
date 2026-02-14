from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: Optional[str] = "redis://localhost:6379"  # Optional with default
    GEMINI_API_KEY: str
    PHONAD_LAB_API_KEY: str
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    GROQ_API_KEY:str
    DEEPGRAM_API_KEY: str

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # This allows extra fields in .env without errors


settings = Settings()
