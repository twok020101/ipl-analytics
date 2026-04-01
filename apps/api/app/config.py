from pydantic_settings import BaseSettings
import os
from pathlib import Path


def _find_env():
    """Find .env file — check cwd, then parent dirs up to 3 levels."""
    for p in [
        Path(".env"),
        Path("../.env"),
        Path("../../.env"),
        Path("../../../.env"),
    ]:
        if p.exists():
            return str(p.resolve())
    return None


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./ipl_analytics.db"
    CRICAPI_KEY: str = ""
    JWT_SECRET: str = ""

    model_config = {
        "env_file": _find_env(),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
