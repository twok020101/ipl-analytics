from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./ipl_analytics.db"
    CRICAPI_KEY: str = ""
    JWT_SECRET: str = ""

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[3] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
