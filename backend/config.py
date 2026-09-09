"""
config.py — Application settings loaded from environment / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Primary DB connection string
    database_url: str = "postgresql://postgres:disha@localhost:5432/youtube_analytics"

    # YouTube
    youtube_api_key: str = ""

    # FastAPI URL (used by Streamlit)
    backend_url: str = "http://localhost:8000"


settings = Settings()
