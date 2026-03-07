"""Mod requests API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.mod import Mod
from app.models.mod_request import ModRequest
from app.schemas.mod_request import ModRequestCreate, ModRequestResponse

router = APIRouter(prefix="/mod-request", tags=["requests"])


@router.post("", response_model=ModRequestResponse)
def create_mod_request(
    request_data: ModRequestCreate,
    db: Session = Depends(get_db),
):
    """Submit a mod request from launcher."""
    # Verify mod exists
    mod = db.query(Mod).filter(Mod.id == request_data.mod_id).first()
    if not mod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mod not found",
        )
    
    # Create request
    mod_request = ModRequest(
        mod_id=request_data.mod_id,
        user_name=request_data.user_name,
        phone=request_data.phone,
        pc_id=request_data.pc_id,
        status="pending",
    )
    
    db.add(mod_request)
    db.commit()
    db.refresh(mod_request)
    
    return mod_request

