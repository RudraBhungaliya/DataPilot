from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path

# Locate root or local .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BASE_DIR.parent.parent
ENV_FILES = [ROOT_DIR / ".env", BASE_DIR / ".env"]
env_file_path = next((f for f in ENV_FILES if f.exists()), None)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_file_path or ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core
    PROJECT_NAME: str = "DataPilot"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    # PostgreSQL Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "datapilot"
    POSTGRES_PASSWORD: str = "datapilot_secret_pass"
    POSTGRES_DB: str = "datapilot_db"
    DATABASE_URL: Union[str, None] = None

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis Configuration Foundation
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Union[str, None] = None
    REDIS_DB: int = 0
    REDIS_URL: Union[str, None] = None

    # AI / LLM Configuration
    AI_PROVIDER: str = "gemini"
    AI_MODEL: str = "gemini-2.5-flash"
    AI_API_KEY: Union[str, None] = None
    GEMINI_API_KEY: Union[str, None] = None
    AI_TIMEOUT_SECONDS: int = 30

    @property
    def effective_ai_api_key(self) -> Union[str, None]:
        return self.AI_API_KEY or self.GEMINI_API_KEY or os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")


settings = Settings()
