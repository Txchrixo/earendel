"""Earendel application configuration (pydantic-settings).

Reads from the project-root .env (shared with the Next.js frontend)
so BACKEND_SECRET + DATABASE_URL are the same on both sides.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
DB_PATH = BACKEND_ROOT / "earendel.db"

# Load the project-root .env so the backend shares secrets with the frontend.
_PROJECT_ENV = PROJECT_ROOT / ".env"
if _PROJECT_ENV.exists():
    for _line in _PROJECT_ENV.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v


class Settings(BaseSettings):
    app_name: str = "Earendel"
    version: str = "0.1.0"
    port: int = 8001
    host: str = "0.0.0.0"
    database_url: str = f"sqlite+aiosqlite:///{DB_PATH}"
    llm_enabled: bool = False
    cors_origins: list[str] = ["*"]
    seed_on_startup: bool = True
    backend_secret: str = os.environ.get("BACKEND_SECRET", "dev-secret-change-me")

    class Config:
        env_prefix = "EARENDEL_"
        env_file = str(_PROJECT_ENV) if _PROJECT_ENV.exists() else ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
