"""License activation API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.license import LicenseActivate, LicenseActivateResponse
from app.services.license_service import LicenseService

router = APIRouter(prefix="/activate-key", tags=["activation"])


@router.post("", response_model=LicenseActivateResponse)
def activate_key(
    activation_data: LicenseActivate,
    db: Session = Depends(get_db),
):
    """Activate a license key for a PC."""
    success, message, license_id = LicenseService.activate_key(
        db=db,
        key=activation_data.key,
        pc_id=activation_data.pc_id,
    )
    
    return LicenseActivateResponse(
        success=success,
        message=message,
        license_id=license_id,
    )

