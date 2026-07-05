from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), extra="ignore")

    # SimpleFIN — setup token (one-time claim) or pre-claimed access URL
    simplefin_token: str | None = None
    simplefin_access_url: str | None = None

    # Database
    database_url: str = "postgresql+asyncpg://finance:devpassword@localhost:5432/finance_tracker"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "dev_jwt_secret_change_in_production_32chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # Encryption
    fernet_key: str = "dev_fernet_key_replace_me_in_production="

    # App — all pages read from local Postgres; SimpleFIN is manual sync only
    backend_cors_origins: str = "http://localhost:5173"
    auto_sync_enabled: bool = False
    sync_interval_hours: int = 24
    simplefin_daily_request_limit: int = 24
    transfer_window_days: int = 2
    simplefin_chunk_days: int = 89
    simplefin_max_backfill_chunks: int = 8

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
