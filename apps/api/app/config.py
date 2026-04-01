from pydantic_settings import BaseSettings
from pathlib import Path
import os


def _find_env_file() -> str:
    """Find .env file — works both locally and in Docker."""
    # Try relative to this file (local dev: apps/api/app/config.py → ../../.env)
    candidates = [
        Path(__file__).resolve().parents[3] / ".env",  # local: /project/.env
        Path(__file__).resolve().parents[2] / ".env",  # docker: /app/.env
        Path("/app/.env"),
        Path(".env"),
    ]
    for p in candidates:
        try:
            if p.exists():
                return str(p)
        except (IndexError, OSError):
            continue
    return ".env"  # fallback — pydantic-settings handles missing file gracefully


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./ipl_analytics.db"
    CRICAPI_KEY: str = ""
    JWT_SECRET: str = ""

    model_config = {
        "env_file": _find_env_file(),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
