"""Application configuration.

The .env path is resolved relative to this file rather than the process CWD,
so the app, the seeder and the tests all read the same file no matter where
they are launched from.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # --- Hindsight Cloud ---------------------------------------------------
    # Single bearer token (starts with hsk_). There is no org/project header:
    # the API scopes everything to a memory bank named in the request path.
    HINDSIGHT_API_KEY: str = ""
    HINDSIGHT_BASE_URL: str = "https://api.hindsight.vectorize.io"
    HINDSIGHT_BANK_ID: str = "clientsense"
    HINDSIGHT_TIMEOUT: float = 120.0

    # --- Application -------------------------------------------------------
    APP_NAME: str = "ClientSense"
    DEBUG: bool = False
    CORS_ORIGINS: str = (
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:5500,http://127.0.0.1:5500"
    )

    # NOTE: there is deliberately no LLM API key here. ClientSense never calls
    # a model directly - Hindsight runs both fact extraction (retain) and
    # reasoning (reflect) server-side using its own configured provider.

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def hindsight_configured(self) -> bool:
        return bool(self.HINDSIGHT_API_KEY and self.HINDSIGHT_BANK_ID)


settings = Settings()
