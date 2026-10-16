from __future__ import annotations

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BLOCKED_MODEL_SCHEMES: tuple[str, ...] = (
    "http://",
    "https://",
    "hf://",
    "s3://",
    "gs://",
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    LOCAL_MODEL_PATH: str = ""
    """Optional dedicated GGUF for JD understanding + extraction (defaults to LOCAL_MODEL_PATH)."""
    LOCAL_MODEL_PATH_JD: str = ""
    """Optional dedicated GGUF for semantic evidence matching (defaults to LOCAL_MODEL_PATH)."""
    LOCAL_MODEL_PATH_EVIDENCE: str = ""
    LOCAL_MODEL_CONTEXT: int = Field(default=4096, ge=512, le=8192)
    LOCAL_MODEL_MAX_TOKENS: int = Field(default=4096, ge=16, le=8192)
    LOCAL_MODEL_JD_UNDERSTANDING_MAX_TOKENS: int = Field(default=768, ge=64, le=4096)
    LOCAL_MODEL_EVIDENCE_MAX_TOKENS: int = Field(default=1536, ge=64, le=8192)
    LOCAL_MODEL_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=2.0)
    LOCAL_INFERENCE_TIMEOUT_SECONDS: int = Field(default=120, ge=1, le=600)
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:8000"
    ENVIRONMENT: str = "development"

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT must be development, test, or production")
        return normalized

    @field_validator("LOCAL_MODEL_PATH")
    @classmethod
    def validate_local_model_path(cls, value: str) -> str:
        stripped = value.strip()
        lowered = stripped.lower()
        if any(lowered.startswith(scheme) for scheme in _BLOCKED_MODEL_SCHEMES):
            raise ValueError("LOCAL_MODEL_PATH must be a local filesystem path, not a URL")
        return stripped

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if not self.is_production:
            return self
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        if not self.allowed_origins_list:
            raise ValueError("ALLOWED_ORIGINS is required in production")
        if "*" in self.allowed_origins_list:
            raise ValueError("Wildcard CORS origins are not allowed in production")
        return self

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [
            origin.strip().rstrip("/")
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]
