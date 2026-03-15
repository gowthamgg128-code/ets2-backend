"""Application configuration and settings."""
from pydantic import field_validator
from pydantic_settings import SettingsConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # App
    DEBUG: bool = False
    APP_NAME: str = "ETS2 Backend"
    ADMIN_PANEL_ORIGIN: str
    LOGIN_RATE_LIMIT: str = "5/minute"
    ACTIVATION_RATE_LIMIT: str = "10/minute"

    # Optional legacy env keys kept for compatibility.
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_URL: str | None = None

    # GitHub-backed encrypted mod storage.
    GITHUB_STORAGE_TOKEN: str | None = None
    GITHUB_STORAGE_REPO: str | None = None
    GITHUB_API_URL: str = "https://api.github.com"

    # Backblaze B2 S3-compatible storage.
    B2_KEY_ID: str
    B2_APPLICATION_KEY: str
    B2_BUCKET_NAME: str
    B2_ENDPOINT: str
    B2_REGION: str

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_value(cls, value):
        """Handle non-boolean DEBUG values from host environments."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        raise ValueError("DEBUG must be boolean-like")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Enforce PostgreSQL/Supabase database URLs."""
        if not value.startswith(
            ("postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://")
        ):
            raise ValueError("DATABASE_URL must use PostgreSQL (Supabase)")
        return value

    @field_validator("ADMIN_PANEL_ORIGIN")
    @classmethod
    def validate_admin_panel_origin(cls, value: str) -> str:
        """Require a concrete admin panel origin for CORS."""
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("ADMIN_PANEL_ORIGIN must be an http(s) origin")
        return normalized

    @field_validator("LOGIN_RATE_LIMIT", "ACTIVATION_RATE_LIMIT")
    @classmethod
    def validate_rate_limit(cls, value: str) -> str:
        """Require non-empty slowapi-compatible rate limit strings."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Rate limit values must be non-empty")
        return normalized

    @field_validator("GITHUB_STORAGE_REPO")
    @classmethod
    def validate_github_storage_repo(cls, value: str | None) -> str | None:
        """Validate GitHub storage repo when legacy GitHub uploads are enabled."""
        if value is None:
            return None
        normalized = value.strip().strip("/")
        parts = normalized.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("GITHUB_STORAGE_REPO must use owner/repo format")
        return normalized

    @field_validator("GITHUB_API_URL")
    @classmethod
    def validate_github_api_url(cls, value: str) -> str:
        """Require a concrete GitHub API base URL."""
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("GITHUB_API_URL must be an http(s) URL")
        return normalized

    @field_validator("B2_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME", "B2_REGION")
    @classmethod
    def validate_non_empty_storage_value(cls, value: str) -> str:
        """Require non-empty B2 configuration values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("B2 configuration values must be non-empty")
        return normalized

    @field_validator("B2_ENDPOINT")
    @classmethod
    def validate_b2_endpoint(cls, value: str) -> str:
        """Require a concrete B2 S3 endpoint."""
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("B2_ENDPOINT must be an http(s) URL")
        return normalized

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
