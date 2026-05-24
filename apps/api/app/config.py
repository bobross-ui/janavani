from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./janavani_test.db"
    redis_url: str = "redis://localhost:6379/0"
    ai_provider: str = "local"
    sarvam_api_key: Optional[str] = None
    sarvam_api_base: str = "https://api.sarvam.ai"
    sarvam_stt_model: str = "saarika:v2.5"
    sarvam_stt_translate_model: str = "saaras:v2.5"
    sarvam_translate_model: str = "mayura:v1"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_chat_model: str = "sarvam-m"
    sarvam_timeout_seconds: float = 30.0
    sarvam_max_retries: int = 2
    sarvam_fallback_on_error: bool = True
    allow_provider_override: bool = False
    clustering_pivot_language: str = "hi"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    return Settings()
