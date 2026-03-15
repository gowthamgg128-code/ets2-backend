"""Mods API endpoints."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.license import License
from app.models.license_key import LicenseKey
from app.models.mod import Mod
from app.schemas.mod import ModDownloadResponse, ModListResponse
from app.services.storage import generate_download_url

router = APIRouter(prefix="/mods", tags=["mods"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ModListResponse])
def list_mods(db: Session = Depends(get_db)):
    """Get all active mods."""
    mods = db.query(Mod).filter(Mod.is_active == True).all()
    return mods


@router.get("/{mod_id}/download", response_model=ModDownloadResponse)
def download_mod(
    mod_id: UUID,
    x_license_key: str | None = Header(None, alias="X-License-Key"),
    x_pc_id: str | None = Header(None, alias="X-PC-ID"),
    db: Session = Depends(get_db),
):
    """Return the stored mod download URL after license checks."""
    if not x_license_key or not x_pc_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid license",
        )

    license_key = db.query(LicenseKey).filter(LicenseKey.key == x_license_key).first()
    if not license_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid license",
        )

    if not license_key.is_used:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="License not activated",
        )

    if str(license_key.mod_id) != str(mod_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid license",
        )

    license_obj = db.query(License).filter(
        License.mod_id == mod_id,
        License.pc_id == x_pc_id,
        License.status == "active",
    ).first()
    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid license",
        )

    mod = db.query(Mod).filter(Mod.id == mod_id).first()
    if not mod or not mod.file_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mod file not found",
        )
    if not mod.checksum or not mod.size:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mod metadata incomplete",
        )

    logger.info(
        "download request validated: mod_id=%s pc_id=%s",
        mod_id,
        x_pc_id,
    )
    storage_key = mod.encrypted_file_path
    if not storage_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mod storage key missing",
        )

    return {
        "download_url": generate_download_url(storage_key),
        "checksum": mod.checksum,
        "size": mod.size,
    }
