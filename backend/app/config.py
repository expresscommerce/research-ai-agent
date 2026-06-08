"""
Agentic AI Research Platform — Configuration.
"""

from __future__ import annotations

from pathlib import Path

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    """Application configuration loaded from .env file."""

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://researcher:researcher_secret@localhost:5432/research_platform"

    # --- Security ---
    SECRET_KEY: str = "change-me"
    ENCRYPTION_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # --- Agent Config ---
    DEFAULT_MODEL: str = "openai/gpt-4o-mini"
    MAX_ITERATIONS: int = 3
    QUALITY_THRESHOLD: int = 75
    AGENT_TIMEOUT: int = 120
    TAVILY_API_KEY: str = ""
    ENABLE_TAVILY: bool = True
    ENABLE_DUCKDUCKGO: bool = True
    ENABLE_ARXIV: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def fernet(self) -> Fernet:
        key = self.ENCRYPTION_KEY
        if not key:
            key = Fernet.generate_key().decode()
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_path.exists():
                content = env_path.read_text()
                content = content.replace("ENCRYPTION_KEY=", f"ENCRYPTION_KEY={key}", 1)
                env_path.write_text(content)
            self.ENCRYPTION_KEY = key
        return Fernet(key.encode() if isinstance(key, str) else key)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings(
    _env_file=str(Path(__file__).resolve().parent.parent.parent / ".env")
)
