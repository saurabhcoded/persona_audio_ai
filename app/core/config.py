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

    # LLM: Gemini on Vertex AI, authenticated via gcloud Application Default Credentials.
    # gcp_project falls back to the ADC / gcloud default project when unset.
    gcp_project: str | None = None
    gcp_location: str = "global"
    llm_chat_model: str = "gemini-3.5-flash-lite"
    llm_chat_thinking: Literal["minimal", "low", "medium", "high"] | None = "minimal"
    llm_chat_temperature: float = 0.9
    llm_build_model: str = "gemini-4-argon"
    llm_classify_model: str = "gemini-3.5-flash-lite"
    chat_max_history: int = 20

    # Personas: storage, upload limits, retrieval
    data_dir: str = "data"
    upload_max_mb: int = 25
    persona_min_messages: int = 30
    persona_max_pairs: int = 3000  # most recent reply pairs embedded per persona
    embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 768
    embedding_concurrency: int = 16
    retrieval_pairs_k: int = 12

    # Fish Audio TTS
    fish_tts_model: str = "s2.1-pro"
    fish_tts_format: Literal["mp3", "wav", "opus"] = "mp3"
    fish_default_voice_id: str | None = None
    tts_max_chars: int = 1000
    # Parallel TTS calls per streamed reply (Fish limits concurrency per account)
    tts_stream_concurrency: int = 2

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
