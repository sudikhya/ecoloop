from pathlib import Path
from typing import List, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "EcoLoop API"
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000
    FIREBASE_PROJECT_ID: str | None = None
    GOOGLE_CLOUD_PROJECT: str | None = None
    GOOGLE_CLOUD_PROJECT_NUMBER: str | None = None
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    MAX_REQUEST_BYTES: int = 256_000
    MAX_PHOTO_BYTES: int = 2_000_000
    MAX_SURPLUS_MEDIA_BYTES: int = 5_000_000
    GEMINI_API_KEY: SecretStr | None = None
    GOOGLE_API_KEY: SecretStr | None = None
    AGENT_ENABLED: bool = False
    AGENT_PROVIDER: Literal["auto", "gemini_api", "vertex"] = "auto"
    AGENT_MODEL: str = "gemini-3.1-flash-lite"
    AGENT_THINKING_LEVEL: Literal["MINIMAL", "LOW", "MEDIUM", "HIGH"] = "MINIMAL"
    PHOTO_MODEL: str = "gemini-3.1-flash-lite"
    PHOTO_THINKING_LEVEL: Literal["MINIMAL", "LOW", "MEDIUM", "HIGH"] = "MINIMAL"
    AGENT_VERTEX_PROJECT_ID: str | None = None
    AGENT_VERTEX_LOCATION: str | None = None
    AGENT_VERTEX_ENGINE_LOCATION: str | None = None
    AGENT_SESSION_STORE: Literal["in_memory", "vertex_ai"] = "in_memory"
    AGENT_VERTEX_ENGINE_ID: str | None = None
    AGENT_SESSION_IDLE_TTL_SECONDS: int = 86_400
    AGENT_MEMORY_BANK_ENABLED: bool = False
    AGENT_REQUEST_TIMEOUT_SECONDS: int = 20
    AGENT_MAX_OUTPUT_TOKENS: int = 4_096
    AI_DAILY_REQUEST_LIMIT: int = 300
    SURPLUS_PILOT_ENABLED: bool = False
    SURPLUS_INTAKE_AGENT_RESOURCE: str | None = None
    COLLECTION_PLANNER_AGENT_RESOURCE: str | None = None
    AGENT_RUNTIME_LOCATION: str = "asia-south1"
    SURPLUS_AGENT_TIMEOUT_SECONDS: int = 25

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return [str(origin).rstrip("/") for origin in v]
        raise ValueError("CORS origins must be a list or comma-separated string")

    @field_validator("GOOGLE_CLOUD_PROJECT_NUMBER")
    @classmethod
    def validate_google_cloud_project_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not 6 <= len(normalized) <= 20 or not normalized.isdigit():
            raise ValueError("GOOGLE_CLOUD_PROJECT_NUMBER must contain 6 to 20 digits")
        return normalized

    @field_validator("BACKEND_CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, origins: List[str]) -> List[str]:
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not permitted")
        return origins

    @field_validator("MAX_REQUEST_BYTES")
    @classmethod
    def validate_request_limit(cls, size: int) -> int:
        if not 1_024 <= size <= 2_000_000:
            raise ValueError("MAX_REQUEST_BYTES must be between 1 KiB and 2 MiB")
        return size

    @field_validator("MAX_PHOTO_BYTES")
    @classmethod
    def validate_photo_limit(cls, size: int) -> int:
        if not 16_384 <= size <= 2_000_000:
            raise ValueError("MAX_PHOTO_BYTES must be between 16 KiB and 2 MiB")
        return size

    @field_validator("MAX_SURPLUS_MEDIA_BYTES")
    @classmethod
    def validate_surplus_media_limit(cls, size: int) -> int:
        if not 16_384 <= size <= 5_000_000:
            raise ValueError("MAX_SURPLUS_MEDIA_BYTES must be between 16 KiB and 5 MiB")
        return size

    @field_validator("AGENT_REQUEST_TIMEOUT_SECONDS")
    @classmethod
    def validate_agent_timeout(cls, seconds: int) -> int:
        if not 1 <= seconds <= 60:
            raise ValueError("AGENT_REQUEST_TIMEOUT_SECONDS must be between 1 and 60")
        return seconds

    @field_validator("SURPLUS_AGENT_TIMEOUT_SECONDS")
    @classmethod
    def validate_surplus_agent_timeout(cls, seconds: int) -> int:
        if not 1 <= seconds <= 60:
            raise ValueError("SURPLUS_AGENT_TIMEOUT_SECONDS must be between 1 and 60")
        return seconds

    @field_validator("AGENT_SESSION_IDLE_TTL_SECONDS")
    @classmethod
    def validate_agent_session_idle_ttl(cls, seconds: int) -> int:
        if not 3_600 <= seconds <= 2_592_000:
            raise ValueError("AGENT_SESSION_IDLE_TTL_SECONDS must be between 1 hour and 30 days")
        return seconds

    @field_validator("AGENT_MAX_OUTPUT_TOKENS")
    @classmethod
    def validate_agent_output_tokens(cls, tokens: int) -> int:
        if not 256 <= tokens <= 8_192:
            raise ValueError("AGENT_MAX_OUTPUT_TOKENS must be between 256 and 8192")
        return tokens

    @field_validator("AI_DAILY_REQUEST_LIMIT")
    @classmethod
    def validate_ai_daily_limit(cls, limit: int) -> int:
        if not 1 <= limit <= 300:
            raise ValueError("AI_DAILY_REQUEST_LIMIT must be between 1 and 300")
        return limit

    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
