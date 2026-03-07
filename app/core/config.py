"""Application configuration and settings."""
from typing import Optional
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
    MASTER_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # GitHub Releases storage
    GITHUB_STORAGE_TOKEN: str
    GITHUB_STORAGE_REPO: str
    GITHUB_API_URL: str = "https://api.github.com"

    # Launcher encryption compatibility
    LAUNCHER_SALT: str = "ETS2_LAUNCHER_SALT_V1"

    # App
    DEBUG: bool = False
    APP_NAME: str = "ETS2 Backend"

    # Optional legacy env keys kept for compatibility.
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Enforce PostgreSQL/Supabase database URLs."""
        if not value.startswith(
            ("postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://")
        ):
            raise ValueError("DATABASE_URL must use PostgreSQL (Supabase)")
        return value

    @field_validator("GITHUB_STORAGE_REPO")
    @classmethod
    def validate_github_repo(cls, value: str) -> str:
        """Ensure repo is in owner/repo format."""
        if value.count("/") != 1:
            raise ValueError("GITHUB_STORAGE_REPO must be in 'owner/repo' format")
        return value

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

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
