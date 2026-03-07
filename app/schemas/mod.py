"""Mod request and response schemas."""
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class ModCreate(BaseModel):
    """Mod creation schema."""
    
    name: str
    version: str
    description: str | None = None


class ModResponse(BaseModel):
    """Mod response schema."""
    
    id: UUID
    name: str
    version: str
    description: str | None = None
    file_url: str | None = None
    size: int | None = None
    checksum: str | None = None
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
    
    class Config:
        from_attributes = True


class ModDownloadResponse(BaseModel):
    """Download URL response schema."""

    download_url: str

