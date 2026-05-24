from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./janavani_test.db"
    redis_url: str = "redis://localhost:6379/0"
    ai_provider: str = "local"
    sarvam_api_key: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    return Settings()
