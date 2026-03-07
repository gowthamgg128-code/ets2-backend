"""License request and response schemas."""
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class LicenseKeyGenerate(BaseModel):
    """Generate license key schema."""
    
    mod_id: UUID
    pc_id: str | None = None


class LicenseKeyResponse(BaseModel):
    """License key response schema."""
    
    id: UUID
    key: str
    mod_id: UUID
    is_used: bool
    created_at: datetime
    used_at: datetime | None = None
    
    class Config:
        from_attributes = True


class LicenseActivate(BaseModel):
    """License activation schema."""
    
    key: str
    pc_id: str


class LicenseActivateResponse(BaseModel):
    """License activation response schema."""
    
    success: bool
    message: str
    license_id: UUID | None = None


class LicenseResponse(BaseModel):
    """License response schema."""
    
    id: UUID
    mod_id: UUID
    pc_id: str
    status: str
    activated_at: datetime
    
    class Config:
        from_attributes = True

