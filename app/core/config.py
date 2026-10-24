from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and `.env`.

    Real environment variables take precedence over values in `.env`,
    so Docker / CI can override anything without touching the file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Fish Audio API"
    app_version: str = "0.1.0"
    environment: Literal["local", "dev", "staging", "prod"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Frontend (built React app; served only if the directory exists)
    frontend_dist_dir: str = "frontend/dist"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # CORS (JSON list in .env, e.g. CORS_ORIGINS=["http://localhost:3000"])
    cors_origins: list[str] = Field(default_factory=list)

    # Secrets / external services
    secret_key: str = "change-me"
    fish_audio_api_key: str | None = None

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
