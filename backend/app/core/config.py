import logging
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MODE: Literal["dev", "prod"] = "dev"
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] = [FRONTEND_URL]
    XENDIT_SECRET_KEY: str = ""
    XENDIT_CALLBACK_TOKEN: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    LOG_SQL: bool = False

    @field_validator("JWT_SECRET")
    @classmethod
    def _strong_secret(cls, v: str) -> str:
        placeholders = {"change-me", "secret", "change-me-to-a-long-random-string", ""}
        if len(v) < 32 or v.lower() in placeholders:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters and not a placeholder. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


try:
    settings = Settings()
except Exception as exc:
    raise RuntimeError(
        "Failed to load settings — check backend/.env or environment variables.\n"
        f"Details: {exc}"
    ) from exc

if settings.MODE == "prod":
    if not settings.XENDIT_SECRET_KEY:
        raise RuntimeError("XENDIT_SECRET_KEY is required when MODE=prod")
    if not settings.XENDIT_CALLBACK_TOKEN:
        raise RuntimeError("XENDIT_CALLBACK_TOKEN is required when MODE=prod")
