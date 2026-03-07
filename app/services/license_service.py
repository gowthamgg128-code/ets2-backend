"""License management service."""
from sqlalchemy.orm import Session
from uuid import UUID
from app.models.license_key import LicenseKey
from app.models.license import License
from app.models.mod import Mod
from datetime import datetime


class LicenseService:
    """Service for license validation and management."""
    
    @staticmethod
    def activate_key(
        db: Session,
        key: str,
        pc_id: str,
    ) -> tuple[bool, str, UUID | None]:
        """
        Activate a license key for a PC.
        
        Args:
            db: Database session
            key: License key to activate
            pc_id: PC identifier from launcher
        
        Returns:
            Tuple of (success, message, license_id)
        """
        # Find the license key
        license_key = db.query(LicenseKey).filter(
            LicenseKey.key == key
        ).first()
        
        if not license_key:
            return False, "Invalid license key", None
        
        if license_key.is_used:
            return False, "License key already used", None
        
        # Check if mod exists
        mod = db.query(Mod).filter(Mod.id == license_key.mod_id).first()
        if not mod:
            return False, "Mod not found", None
        
        # Check if license already exists for this PC and mod
        existing_license = db.query(License).filter(
            License.mod_id == license_key.mod_id,
            License.pc_id == pc_id,
            License.status == "active",
        ).first()
        
        if existing_license:
            return True, "License already active for this PC", existing_license.id
        
        # Create new license
        license_obj = License(
            mod_id=license_key.mod_id,
            pc_id=pc_id,
            status="active",
        )
        
        db.add(license_obj)
        
        # Mark key as used
        license_key.is_used = True
        license_key.used_at = datetime.utcnow()
        
        db.commit()
        db.refresh(license_obj)
        
        return True, "License activated successfully", license_obj.id
    
    @staticmethod
    def check_license(
        db: Session,
        mod_id: UUID,
        pc_id: str,
    ) -> bool:
        """
        Check if a PC has an active license for a mod.
        
        Args:
            db: Database session
            mod_id: Mod ID to check
            pc_id: PC identifier
        
        Returns:
            True if license is active
        """
        license_obj = db.query(License).filter(
            License.mod_id == mod_id,
            License.pc_id == pc_id,
            License.status == "active",
        ).first()
        
        return license_obj is not None
    
    @staticmethod
    def revoke_license(db: Session, license_id: UUID) -> bool:
        """
        Revoke a license.
        
        Args:
            db: Database session
            license_id: License ID to revoke
        
        Returns:
            True if revoked successfully
        """
        license_obj = db.query(License).filter(
            License.id == license_id
        ).first()
        
        if not license_obj:
            return False
        
        license_obj.status = "revoked"
        db.commit()
        
        return True

