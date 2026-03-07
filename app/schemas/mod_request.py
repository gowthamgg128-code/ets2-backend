"""Mod request request and response schemas."""
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class ModRequestCreate(BaseModel):
    """Mod request creation schema."""
    
    mod_id: UUID
    user_name: str
    phone: str
    pc_id: str


class ModRequestResponse(BaseModel):
    """Mod request response schema."""
    
    id: UUID
    mod_id: UUID
    user_name: str
    phone: str
    pc_id: str
    status: str
    created_at: datetime
    license_key: str | None = None
    
    class Config:
        from_attributes = True

