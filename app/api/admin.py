"""Admin API endpoints."""
import hashlib
import hmac
import logging
from datetime import timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.models.admin import Admin
from app.models.license import License
from app.models.license_key import LicenseKey
from app.models.mod import Mod
from app.models.mod_request import ModRequest
from app.schemas.admin import AdminLogin, AdminToken
from app.schemas.license import LicenseKeyGenerate, LicenseKeyResponse, LicenseResponse
from app.schemas.mod import ModCreate, ModResponse, ModUploadMetadata
from app.schemas.mod_request import ModRequestResponse
from app.services.storage import generate_upload_url, head_uploaded_object

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()
MAX_ENCRYPTED_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024


class UploadTargetRequest(BaseModel):
    """Request body for encrypted mod asset upload targets."""

    filename: str
    size: int
    content_type: str


class UploadTargetResponse(BaseModel):
    """Direct upload target details for the admin frontend."""

    upload_url: str
    file_url: str
    storage_key: str
    method: str
    headers: dict[str, str] | None = None


def _build_deterministic_key(mod_id: str, pc_id: str) -> str:
    """Build a deterministic key for mod + PC without schema changes."""
    message = f"{mod_id}:{pc_id}".encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).hexdigest().upper()
    return digest[:32]


def _get_legacy_key_if_safe(db: Session, mod_id) -> LicenseKey | None:
    """Fallback for existing data when only one PC exists for the mod."""
    distinct_pc_count = db.query(ModRequest.pc_id).filter(ModRequest.mod_id == mod_id).distinct().count()
    if distinct_pc_count != 1:
        return None
    return db.query(LicenseKey).filter(LicenseKey.mod_id == mod_id).order_by(LicenseKey.created_at.desc()).first()


def _storage_key_from_file_url(file_url: str) -> str:
    parsed = urlparse(file_url)
    path = parsed.path.strip("/")
    expected_prefix = f"{settings.B2_BUCKET_NAME}/"
    if not path.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_url does not point to the configured storage bucket",
        )
    return path[len(expected_prefix):]


@router.post("/login", response_model=AdminToken)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(
    request: Request,
    credentials: AdminLogin,
    db: Session = Depends(get_db),
):
    """Admin login endpoint."""
    logger.info("Login attempt: username=%s", credentials.username)

    try:
        admin = db.query(Admin).filter(Admin.username == credentials.username).first()
    except OperationalError:
        logger.exception("Database unavailable during login for username=%s", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        )
    except Exception:
        logger.exception("Database error during login query for username=%s", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    if not admin:
        logger.warning("Failed login attempt - user not found: username=%s", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    from app.core.security import verify_password
    try:
        password_ok = verify_password(credentials.password, admin.password_hash)
    except Exception:
        logger.exception("Password verification error for username=%s", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    if not password_ok:
        logger.warning("Failed login attempt - invalid password: username=%s", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    try:
        access_token = create_access_token(
            data={"sub": str(admin.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    except Exception:
        logger.exception("Token generation error for admin_id=%s", admin.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    logger.info(
        "Admin login successful: username=%s admin_id=%s",
        credentials.username,
        admin.id,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/upload-mod", response_model=ModResponse)
def upload_mod(
    payload: ModUploadMetadata,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Store mod metadata after frontend-side encryption and upload."""
    try:
        mod_data = ModCreate(
            name=payload.name,
            version=payload.version,
            description=payload.description,
            file_url=payload.file_url,
            image_url=payload.image_url,
            size=payload.size,
            checksum=payload.checksum,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    try:
        storage_key = payload.storage_key or _storage_key_from_file_url(mod_data.file_url)
        uploaded_object = head_uploaded_object(storage_key)
        if int(uploaded_object["content_length"] or 0) != mod_data.size:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uploaded object size does not match submitted size",
            )

        logger.info(
            "mod metadata create started: name=%s version=%s admin_id=%s storage_key=%s",
            mod_data.name,
            mod_data.version,
            current_admin.id,
            storage_key,
        )

        mod = Mod(
            name=mod_data.name,
            version=mod_data.version,
            description=mod_data.description,
            encrypted_file_path=storage_key,
            file_url=mod_data.file_url,
            image_url=mod_data.image_url,
            size=mod_data.size,
            checksum=mod_data.checksum,
            is_active=True,
        )

        db.add(mod)
        db.commit()
        db.refresh(mod)

        logger.info(
            "database record created: mod_id=%s name=%s version=%s",
            mod.id,
            mod.name,
            mod.version,
        )

        return mod
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded object not found in storage",
        ) from exc
    except HTTPException:
        raise
    except OperationalError as exc:
        logger.exception("Database unavailable during mod metadata create")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        ) from exc
    except Exception as exc:
        logger.exception("mod metadata create failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mod metadata create failed",
        ) from exc


@router.post("/mod-upload-target", response_model=UploadTargetResponse)
def create_upload_target(
    data: UploadTargetRequest,
    current_admin: Admin = Depends(get_current_admin),
):
    """Return a presigned Backblaze B2 upload target for encrypted mods."""
    filename = data.filename.strip()
    content_type = data.content_type.strip()

    if not filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filename must be a plain file name",
        )
    if not filename.lower().endswith(".enc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .enc files allowed",
        )
    if data.size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="size must be greater than 0",
        )
    if data.size > MAX_ENCRYPTED_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large",
        )
    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content_type is required",
        )

    try:
        upload = generate_upload_url(filename=filename, content_type=content_type)
    except Exception as exc:
        logger.exception("Failed to generate B2 upload target")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate upload target",
        ) from exc

    logger.info(
        "Generated mod upload target: admin_id=%s filename=%s size=%s storage_key=%s",
        current_admin.id,
        filename,
        data.size,
        upload.get("storage_key"),
    )

    return UploadTargetResponse(**upload)


@router.get("/mod-requests")
def get_mod_requests(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get all mod requests with mod name and description."""

    requests = db.query(ModRequest).all()
    response_items = []

    for mod_request in requests:
        # 🔥 Get mod details
        mod = db.query(Mod).filter(Mod.id == mod_request.mod_id).first()

        # 🔐 License key logic (same as before)
        license_key = None
        if mod_request.pc_id:
            deterministic_key = _build_deterministic_key(
                mod_request.mod_id,
                mod_request.pc_id,
            )
            existing_key = db.query(LicenseKey).filter(
                LicenseKey.key == deterministic_key
            ).first()

            if existing_key:
                license_key = existing_key.key
            else:
                legacy_key = _get_legacy_key_if_safe(db, mod_request.mod_id)
                if legacy_key:
                    license_key = legacy_key.key

        # ✅ New response
        response_items.append(
            {
                "id": str(mod_request.id),
                "mod_id": str(mod_request.mod_id),
                "user_name": mod_request.user_name,
                "phone": mod_request.phone,
                "pc_id": mod_request.pc_id,
                "status": mod_request.status.title(),

                # 🔥 NEW
                "mod_name": mod.name if mod else "Unknown",
                "description": mod.description if mod else "",

                "license_key": license_key,
            }
        )

    return response_items


@router.post("/generate-key", response_model=LicenseKeyResponse)
def generate_key(
    key_data: LicenseKeyGenerate,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Generate a new license key."""
    mod = db.query(Mod).filter(Mod.id == key_data.mod_id).first()
    if not mod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mod not found",
        )

    pc_id = key_data.pc_id
    mod_request = None
    if pc_id:
        mod_request = db.query(ModRequest).filter(
            ModRequest.mod_id == key_data.mod_id,
            ModRequest.pc_id == pc_id,
        ).order_by(ModRequest.created_at.desc()).first()
    else:
        mod_request = db.query(ModRequest).filter(
            ModRequest.mod_id == key_data.mod_id,
        ).order_by(ModRequest.created_at.desc()).first()
        if mod_request:
            pc_id = mod_request.pc_id

    if not pc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pc_id is required to generate a per-PC license key",
        )

    deterministic_key = _build_deterministic_key(key_data.mod_id, pc_id)
    existing_key = db.query(LicenseKey).filter(
        LicenseKey.key == deterministic_key
    ).first()
    if existing_key:
        if mod_request and mod_request.status != "approved":
            mod_request.status = "approved"
            db.commit()
        return existing_key

    legacy_key = _get_legacy_key_if_safe(db, key_data.mod_id)
    if legacy_key:
        if mod_request and mod_request.status != "approved":
            mod_request.status = "approved"
            db.commit()
        return legacy_key

    license_key = LicenseKey(
        key=deterministic_key,
        mod_id=key_data.mod_id,
        is_used=False,
    )

    db.add(license_key)
    if mod_request and mod_request.status != "approved":
        mod_request.status = "approved"
    db.commit()
    db.refresh(license_key)

    logger.info(
        "License key generated: key_id=%s mod_id=%s admin_id=%s",
        license_key.id,
        license_key.mod_id,
        current_admin.id,
    )

    return license_key


@router.get("/licenses", response_model=list[LicenseResponse])
def get_licenses(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get active licenses plus approved requests with generated keys."""
    active_licenses = db.query(License).filter(License.status == "active").all()

    license_rows = [
        {
            "id": lic.id,
            "mod_id": lic.mod_id,
            "pc_id": lic.pc_id,
            "status": lic.status,
            "activated_at": lic.activated_at,
        }
        for lic in active_licenses
    ]
    seen_pairs = {(str(lic.mod_id), lic.pc_id) for lic in active_licenses}

    approved_requests = db.query(ModRequest).filter(
        func.lower(ModRequest.status) == "approved"
    ).order_by(ModRequest.created_at.desc()).all()

    deterministic_keys = [
        _build_deterministic_key(req.mod_id, req.pc_id)
        for req in approved_requests
        if req.pc_id
    ]
    existing_keys = db.query(LicenseKey).filter(
        LicenseKey.key.in_(deterministic_keys)
    ).all() if deterministic_keys else []
    key_by_value = {k.key: k for k in existing_keys}

    for req in approved_requests:
        pair = (str(req.mod_id), req.pc_id)
        if pair in seen_pairs:
            continue

        key_obj = key_by_value.get(_build_deterministic_key(req.mod_id, req.pc_id))
        if key_obj is None:
            key_obj = _get_legacy_key_if_safe(db, req.mod_id)
        if key_obj is None:
            continue

        license_rows.append(
            {
                "id": key_obj.id,
                "mod_id": req.mod_id,
                "pc_id": req.pc_id,
                "status": "approved",
                "activated_at": key_obj.created_at,
            }
        )
        seen_pairs.add(pair)

    license_rows.sort(key=lambda row: row["activated_at"], reverse=True)
    return license_rows
