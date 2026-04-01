from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./ipl_analytics.db"
    CRICAPI_KEY: str = ""
    JWT_SECRET: str = ""

    model_config = {
        "env_file": ".env" if os.path.exists(".env") else None,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
