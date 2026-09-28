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

    @property
    def redis_connection_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # AI / LLM Configuration
    AI_PROVIDER: str = "groq"
    AI_MODEL: str = "llama-3.3-70b-versatile"
    AI_API_KEY: Union[str, None] = None
    GROQ_API_KEY: Union[str, None] = None
    GEMINI_API_KEY: Union[str, None] = None
    AI_FALLBACK_MODELS: List[str] = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
    ]
    AI_TIMEOUT_SECONDS: int = 30

    @property
    def effective_ai_api_key(self) -> Union[str, None]:
        """
        Returns the API key matching the configured provider.

        A provider-specific key is never mixed with another provider's key. An
        explicit generic AI_API_KEY always takes precedence.
        """
        provider = (self.AI_PROVIDER or "groq").strip().lower()
        if provider in ("gemini", "google"):
            specific = self.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        elif provider in ("groq", "llama"):
            specific = self.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        else:
            specific = (
                self.GROQ_API_KEY
                or self.GEMINI_API_KEY
                or os.getenv("GROQ_API_KEY")
                or os.getenv("GEMINI_API_KEY")
            )
        return self.AI_API_KEY or os.getenv("AI_API_KEY") or specific

    # Source Collection Engine Configuration (Phase 4)
    DATAPILOT_HTTP_TIMEOUT: int = 20
    DATAPILOT_HTTP_MAX_RETRIES: int = 3
    DATAPILOT_HTTP_USER_AGENT: str = "DataPilot/0.1 (+https://github.com/RudraBhungaliya/DataPilot)"
    DATAPILOT_REQUESTS_PER_DOMAIN: int = 5
    DATAPILOT_MIN_REQUEST_INTERVAL: float = 0.5  # seconds between requests to same domain
    DATAPILOT_MAX_DOCUMENT_SIZE_MB: int = 10
    DATAPILOT_ROBOTS_ENFORCED: bool = False  # enable robots.txt fetching + enforcement (recommended in production)
    DATAPILOT_MAX_HUMAN_ATTEMPTS: int = 3  # max human-in-the-loop CAPTCHA retries before blocking a source
    DATAPILOT_CACHE_MAX_ENTRIES: int = 1000  # in-memory document cache bound
    DATAPILOT_MAX_IN_MEMORY_JOBS: int = 200  # bound for in-memory collection job fallback store
    ZYTE_API_KEY: Union[str, None] = None
    ZYTE_API_URL: str = "https://api.zyte.com/v1/extract"

    # Human-in-the-Loop Notification / Email Configuration
    DATAPILOT_AUTH_EMAIL: Union[str, None] = "client@datapilot.local"
    SMTP_HOST: Union[str, None] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Union[str, None] = None
    SMTP_PASSWORD: Union[str, None] = None
    SMTP_FROM_EMAIL: str = "noreply@datapilot.local"
    SMTP_USE_TLS: bool = True

    # Phase 7: Security / Production
    AUTH_ENABLED: bool = False  # enable API-key auth (turn on in production)
    BOOTSTRAP_API_KEY: Union[str, None] = None  # admin key for first-run key provisioning
    RATE_LIMIT_PER_MINUTE: int = 0  # 0 disables rate limiting
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RUN_EMBEDDED_WORKER: bool = True  # run the background job worker in-process
    WORKER_CONCURRENCY: int = 2
    METRICS_ENABLED: bool = True


settings = Settings()
