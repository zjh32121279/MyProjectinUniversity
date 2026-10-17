from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel


AI_ENGINE_ENV_KEYS = (
    "BOOKFLOW_AI_ENGINE_BASE_URL",
    "BOOKFLOW_AI_ENGINE_API_KEY",
    "BOOKFLOW_AI_ENGINE_NAME",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env_file(env_path: str | Path | None = None) -> dict[str, str]:
    path = Path(env_path) if env_path is not None else project_root() / ".env"
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


load_env_file()


class Settings(BaseModel):
    database_url: str = os.getenv("BOOKFLOW_DATABASE_URL", f"sqlite:///{(project_root() / 'data' / 'bookflow.db').as_posix()}")
    app_name: str = "BookFlow Core"
    secret_key: str = os.getenv("BOOKFLOW_SECRET_KEY", "")
    ai_engine_base_url: str | None = os.getenv("BOOKFLOW_AI_ENGINE_BASE_URL")
    ai_engine_api_key: str | None = os.getenv("BOOKFLOW_AI_ENGINE_API_KEY")
    ai_engine_name: str | None = os.getenv("BOOKFLOW_AI_ENGINE_NAME")
    smtp_host: str = os.getenv("BOOKFLOW_SMTP_HOST", "")
    smtp_port: int = int(os.getenv("BOOKFLOW_SMTP_PORT", "465"))
    smtp_user: str = os.getenv("BOOKFLOW_SMTP_USER", "")
    smtp_password: str = os.getenv("BOOKFLOW_SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("BOOKFLOW_SMTP_FROM", "")
    debug_verification_code: bool = os.getenv("BOOKFLOW_DEBUG_VERIFICATION_CODE", "false").strip().lower() in {"1", "true", "yes", "on"}


settings = Settings()


def smtp_enabled() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def set_database_url(url: str) -> None:
    settings.database_url = url


def reload_settings(env_path: str | Path | None = None) -> Settings:
    load_env_file(env_path)
    settings.database_url = os.getenv("BOOKFLOW_DATABASE_URL", settings.database_url)
    settings.secret_key = os.getenv("BOOKFLOW_SECRET_KEY", settings.secret_key)
    settings.ai_engine_base_url = os.getenv("BOOKFLOW_AI_ENGINE_BASE_URL")
    settings.ai_engine_api_key = os.getenv("BOOKFLOW_AI_ENGINE_API_KEY")
    settings.ai_engine_name = os.getenv("BOOKFLOW_AI_ENGINE_NAME")
    return settings


def ai_engine_config(env_path: str | Path | None = None) -> dict[str, str | None]:
    load_env_file(env_path)
    return {
        "base_url": os.getenv("BOOKFLOW_AI_ENGINE_BASE_URL"),
        "api_key": os.getenv("BOOKFLOW_AI_ENGINE_API_KEY"),
        "model": os.getenv("BOOKFLOW_AI_ENGINE_NAME"),
    }
