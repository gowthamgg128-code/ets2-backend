"""License database model."""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.core.database import Base


class License(Base):
    """License model for activated licenses per PC."""
    
    __tablename__ = "licenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mod_id = Column(UUID(as_uuid=True), ForeignKey("mods.id"), nullable=False)
    pc_id = Column(String(255), nullable=False, index=True)
    status = Column(String(50), default="active", nullable=False)  # active, revoked
    activated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

