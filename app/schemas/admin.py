"""Admin request and response schemas."""
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class AdminLogin(BaseModel):
    """Admin login request schema."""
    
    username: str
    password: str


class AdminToken(BaseModel):
    """Admin token response schema."""
    
    access_token: str
    token_type: str


class AdminCreate(BaseModel):
    """Admin creation schema."""
    
    username: str
    password: str


class AdminResponse(BaseModel):
    """Admin response schema."""
    
    id: UUID
    username: str
    created_at: datetime
    
    class Config:
        from_attributes = True

