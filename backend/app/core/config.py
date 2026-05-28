from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "production", "test"] = "development"

    database_url: str = Field(..., description="postgresql+asyncpg://...")
    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    max_bot_token: str = Field(...)
    max_api_base_url: str = "https://platform-api.max.ru"
    max_transport: Literal["long_poll", "webhook"] = "long_poll"
    webhook_secret: str = Field(..., min_length=5)

    qr_server_secret: str = Field(..., min_length=32)
    qr_bucket_seconds: int = 30
    qr_fuzz_window: int = 1
    qr_session_ttl_seconds: int = 900
    qr_rotation_tick_seconds: int = 15

    upload_dir: str = "/data/uploads"
    upload_max_bytes: int = 10 * 1024 * 1024

    public_base_url: str = ""

    # ссылка на MAX-бота для QR-приглашений (например, https://max.ru/our_bot)
    bot_share_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
