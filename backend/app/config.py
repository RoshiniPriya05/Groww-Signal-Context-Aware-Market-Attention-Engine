import json
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    env: str = "development"
    postgres_user: str = "groww_admin"
    postgres_password: str = "groww_secure_pass"
    postgres_db: str = "groww_signal_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = "postgresql://groww:groww@localhost:5432/groww_signal"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    firebase_credentials_json: str = ""
    cors_origins: str = "http://localhost:3000"
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"
    demo_user_id: str = "00000000-0000-4000-8000-000000000001"


settings = Settings()


def configured_cors_origins() -> list[str]:
    """Accept either the documented JSON list or the legacy comma-separated form."""
    raw = settings.cors_origins.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = [origin.strip() for origin in raw.split(",")]
    if isinstance(parsed, list):
        return [str(origin).strip() for origin in parsed if str(origin).strip()]
    return [raw] if raw else []


def validate_optional_integrations() -> None:
    if not settings.firebase_credentials_json:
        logger.warning("FIREBASE_CREDENTIALS_JSON is not configured; push alerts are disabled.")
    if not settings.posthog_api_key:
        logger.warning("POSTHOG_API_KEY is not configured; telemetry is disabled.")
