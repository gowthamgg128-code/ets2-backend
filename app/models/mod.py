"""Mod database model."""
from sqlalchemy import Column, String, DateTime, Boolean, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.core.database import Base


class Mod(Base):
    """Mod metadata model for storing uploaded mods."""
    
    __tablename__ = "mods"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=True)
    encrypted_file_path = Column(String(500), nullable=True)  # Legacy, unused for downloads.
    file_url = Column(String(1000), nullable=True)
    size = Column(BigInteger, nullable=True)
    checksum = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

