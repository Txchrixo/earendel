"""Earendel application configuration (pydantic-settings)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


BACKEND_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_ROOT / "earendel.db"


class Settings(BaseSettings):
    app_name: str = "Earendel"
    version: str = "0.1.0"
    # Port the FastAPI service listens on. The Next.js frontend reaches it via
    # the Caddy gateway using the XTransformPort query param.
    port: int = 8001
    host: str = "0.0.0.0"
    database_url: str = f"sqlite+aiosqlite:///{DB_PATH}"
    # LLM provider base (used by repair proposer + compiler). Optional.
    llm_enabled: bool = False
    cors_origins: list[str] = ["*"]
    # Seeded demo flag — re-seed the DB on startup when True.
    seed_on_startup: bool = True

    class Config:
        env_prefix = "EARENDEL_"
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
