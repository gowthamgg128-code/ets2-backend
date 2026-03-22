"""Mod request and response schemas."""
import re

from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID


class ModCreate(BaseModel):
    """Mod creation schema."""

    name: str
    version: str
    description: str | None = None
    file_url: str
    size: int
    checksum: str
    image_url: str | None = None  # ✅ NEW

    @field_validator("name", "version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject blank metadata fields after trimming."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        """Normalize optional description input."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("file_url")
    @classmethod
    def validate_file_url(cls, value: str) -> str:
        """Accept HTTPS asset URLs from external storage."""
        normalized = value.strip()
        pattern = r"^https://[^?\s]+$"
        if not re.match(pattern, normalized):
            raise ValueError("file_url must be an https asset URL")
        return normalized

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: int) -> int:
        """Require positive file sizes."""
        if value <= 0:
            raise ValueError("size must be greater than 0")
        return value

    @field_validator("checksum")
    @classmethod
    def validate_checksum(cls, value: str) -> str:
        """Normalize and validate SHA-256 checksums."""
        normalized = value.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("checksum must be a 64-character SHA-256 hex string")
        return normalized


class ModUploadMetadata(ModCreate):
    """Admin metadata payload submitted after direct storage upload."""

    storage_key: str | None = None
    mime_type: str | None = None
    original_filename: str | None = None


class ModResponse(BaseModel):
    """Mod response schema."""

    id: UUID
    name: str
    version: str
    description: str | None = None
    file_url: str | None = None
    size: int | None = None
    checksum: str | None = None
    image_url: str | None = None  # ✅ NEW
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ModListResponse(BaseModel):
    """Mod list response schema (for launcher)."""

    id: UUID
    name: str
    version: str
    description: str | None = None
    size: int | None = None
    image_url: str | None = None  # ✅ NEW

    class Config:
        from_attributes = True


class ModDownloadResponse(BaseModel):
    """Download URL response schema."""

    download_url: str
    checksum: str
    size: int
