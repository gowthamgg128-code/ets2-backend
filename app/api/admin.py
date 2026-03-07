"""Admin API endpoints."""
import hashlib
import hmac
import logging
import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.admin import Admin
from app.models.mod import Mod
from app.models.mod_request import ModRequest
from app.models.license_key import LicenseKey
from app.models.license import License
from app.schemas.admin import AdminLogin, AdminToken
from app.schemas.mod import ModCreate, ModResponse
from app.schemas.mod_request import ModRequestResponse
from app.schemas.license import LicenseKeyGenerate, LicenseKeyResponse, LicenseResponse
from app.api.deps import get_current_admin
from app.services.encryption import EncryptionService
from app.services.github_storage_service import GitHubStorageError, GitHubStorageService
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


def _build_deterministic_key(mod_id: str, pc_id: str) -> str:
    """Build a deterministic key for mod + PC without schema changes."""
    message = f"{mod_id}:{pc_id}".encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).hexdigest().upper()
    return digest[:32]


def _get_legacy_key_if_safe(db: Session, mod_id) -> LicenseKey | None:
    """Fallback for existing data when only one PC exists for the mod."""
    distinct_pc_count = db.query(ModRequest.pc_id).filter(
        ModRequest.mod_id == mod_id
    ).distinct().count()
    if distinct_pc_count != 1:
        return None
    return db.query(LicenseKey).filter(
        LicenseKey.mod_id == mod_id
    ).order_by(LicenseKey.created_at.desc()).first()


@router.post("/login", response_model=AdminToken)
def login(
    credentials: AdminLogin,
    db: Session = Depends(get_db),
):
    """Admin login endpoint."""
    logger.info("Login attempt: username=%s", credentials.username)
    
    try:
        admin = db.query(Admin).filter(Admin.username == credentials.username).first()
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
    name: str = Form(...),
    version: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Upload a mod file (encrypted)."""
    tmp_path: str | None = None
    encrypted_tmp_path: str | None = None
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid upload filename",
            )

        cleaned_name = name.strip()
        cleaned_version = version.strip()
        if not cleaned_name or not cleaned_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mod name and version are required",
            )

        mod_data = ModCreate(
            name=cleaned_name,
            version=cleaned_version,
            description=description,
        )

        logger.info(
            "admin upload started: name=%s version=%s admin_id=%s",
            mod_data.name,
            mod_data.version,
            current_admin.id,
        )

        # Save uploaded file to temporary location.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".scs") as tmp_file:
            tmp_path = tmp_file.name
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                tmp_file.write(chunk)

        logger.info(
            "file encryption started: name=%s version=%s admin_id=%s",
            mod_data.name,
            mod_data.version,
            current_admin.id,
        )
        encryption_service = EncryptionService()
        encrypted_filename = f"{mod_data.name}_{mod_data.version}.enc"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".enc") as encrypted_tmp:
            encrypted_tmp_path = encrypted_tmp.name
        encryption_service.encrypt_file(tmp_path, encrypted_tmp_path)

        logger.info(
            "github upload started: filename=%s admin_id=%s",
            encrypted_filename,
            current_admin.id,
        )
        try:
            github_storage = GitHubStorageService()
            download_url = github_storage.upload_encrypted_file(
                encrypted_tmp_path,
                encrypted_filename,
            )
        except GitHubStorageError as exc:
            logger.warning(
                "github upload failed: status=%s detail=%s filename=%s",
                exc.status_code,
                exc.detail,
                encrypted_filename,
            )
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        logger.info("github upload completed: filename=%s", encrypted_filename)

        file_size = os.path.getsize(encrypted_tmp_path)
        checksum: str | None = None
        with open(encrypted_tmp_path, "rb") as encrypted_file:
            hasher = hashlib.sha256()
            for chunk in iter(lambda: encrypted_file.read(1024 * 1024), b""):
                hasher.update(chunk)
            checksum = hasher.hexdigest()

        mod = Mod(
            name=mod_data.name,
            version=mod_data.version,
            description=mod_data.description,
            encrypted_file_path="github://deprecated",
            file_url=download_url,
            size=file_size,
            checksum=checksum,
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("mod upload failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mod upload failed",
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if encrypted_tmp_path and os.path.exists(encrypted_tmp_path):
            os.unlink(encrypted_tmp_path)


@router.get("/mod-requests", response_model=list[ModRequestResponse])
def get_mod_requests(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get all mod requests."""
    requests = db.query(ModRequest).all()
    response_items: list[ModRequestResponse] = []
    for mod_request in requests:
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

        response_items.append(
            ModRequestResponse(
                id=mod_request.id,
                mod_id=mod_request.mod_id,
                user_name=mod_request.user_name,
                phone=mod_request.phone,
                pc_id=mod_request.pc_id,
                status=mod_request.status.title(),
                created_at=mod_request.created_at,
                license_key=license_key,
            )
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

    # Start with activated licenses.
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

    # Also include approved requests that have a generated key but are not activated yet.
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

