"""License activation API endpoints."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.license import LicenseActivate, LicenseActivateResponse
from app.services.license_service import LicenseService

router = APIRouter(prefix="/activate-key", tags=["activation"])
settings = get_settings()


@router.post("", response_model=LicenseActivateResponse)
@limiter.limit(settings.ACTIVATION_RATE_LIMIT)
def activate_key(
    request: Request,
    activation_data: LicenseActivate,
    db: Session = Depends(get_db),
):
    """Activate a license key for a PC."""
    success, message, license_id, mod_id, mod_name = LicenseService.activate_key(
        db=db,
        key=activation_data.key,
        pc_id=activation_data.pc_id,
        mod_id=activation_data.mod_id,
    )

    return LicenseActivateResponse(
        success=success,
        message=message,
        license_id=license_id,
        mod_id=mod_id,
        mod_name=mod_name,
    )
