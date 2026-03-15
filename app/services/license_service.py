"""License management service."""
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.license import License
from app.models.license_key import LicenseKey
from app.models.mod import Mod


class LicenseService:
    """Service for license validation and management."""

    @staticmethod
    def activate_key(
        db: Session,
        key: str,
        pc_id: str,
        mod_id: UUID | None = None,
    ) -> tuple[bool, str, UUID | None, UUID | None, str | None]:
        """
        Activate a license key for a PC.

        Args:
            db: Database session
            key: License key to activate
            pc_id: PC identifier from launcher
            mod_id: Optional selected mod identifier for launcher validation

        Returns:
            Tuple of (success, message, license_id, mod_id, mod_name)
        """
        license_key = db.query(LicenseKey).filter(LicenseKey.key == key).first()
        if not license_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid license key",
            )

        if mod_id is not None and license_key.mod_id != mod_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This license key is not valid for the selected mod.",
            )

        mod = db.query(Mod).filter(Mod.id == license_key.mod_id).first()
        if not mod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mod not found",
            )

        existing_license = db.query(License).filter(
            License.mod_id == license_key.mod_id,
            License.pc_id == pc_id,
            License.status == "active",
        ).first()
        if existing_license:
            return True, "License already active for this PC", existing_license.id, mod.id, mod.name

        if license_key.is_used:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="License key already used",
            )

        license_obj = License(
            mod_id=license_key.mod_id,
            pc_id=pc_id,
            status="active",
        )
        db.add(license_obj)

        license_key.is_used = True
        license_key.used_at = datetime.utcnow()

        db.commit()
        db.refresh(license_obj)

        return True, "License activated successfully", license_obj.id, mod.id, mod.name

    @staticmethod
    def check_license(
        db: Session,
        mod_id: UUID,
        pc_id: str,
    ) -> bool:
        """
        Check if a PC has an active license for a mod.
        """
        license_obj = db.query(License).filter(
            License.mod_id == mod_id,
            License.pc_id == pc_id,
            License.status == "active",
        ).first()

        return license_obj is not None

    @staticmethod
    def revoke_license(db: Session, license_id: UUID) -> bool:
        """Revoke a license."""
        license_obj = db.query(License).filter(License.id == license_id).first()
        if not license_obj:
            return False

        license_obj.status = "revoked"
        db.commit()
        return True
