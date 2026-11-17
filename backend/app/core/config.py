"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "PayGuard"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "SANDBOX"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = f"sqlite:///{(PROJECT_ROOT / 'payguard.db').as_posix()}"
    TEST_DATABASE_URL: str = f"sqlite:///{(PROJECT_ROOT / 'payguard_test.db').as_posix()}"

    WEBHOOK_SECRET: str = "whsec_sandbox_payguard_local_dev_secret"
    API_AUTH_TOKEN: str = "pg_sandbox_valid_token_2026"
    EXPIRED_AUTH_TOKEN: str = "pg_sandbox_expired_token_2025"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()

