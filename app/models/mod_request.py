"""Mod request database model."""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.core.database import Base


class ModRequest(Base):
    """Mod request model for tracking user requests."""
    
    __tablename__ = "mod_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mod_id = Column(UUID(as_uuid=True), ForeignKey("mods.id"), nullable=False)
    user_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    pc_id = Column(String(255), nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, approved
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

