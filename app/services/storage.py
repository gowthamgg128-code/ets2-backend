"""Backblaze B2 direct-upload helpers."""
import re
import uuid
from urllib.parse import quote, urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()
s3_client = boto3.client(
    "s3",
    endpoint_url=settings.B2_ENDPOINT,
    region_name=settings.B2_REGION,
    aws_access_key_id=settings.B2_KEY_ID,
    aws_secret_access_key=settings.B2_APPLICATION_KEY,
    config=Config(signature_version="s3v4"),
)


def _sanitize_filename(filename: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-.")
    return normalized or f"mod-{uuid.uuid4().hex}.enc"


def _build_file_url(storage_key: str) -> str:
    parsed = urlparse(settings.B2_ENDPOINT)
    base_path = parsed.path.rstrip("/")
    encoded_key = quote(storage_key, safe="/")
    bucket_path = f"{settings.B2_BUCKET_NAME}/{encoded_key}"
    path = f"{base_path}/{bucket_path}" if base_path else f"/{bucket_path}"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def generate_upload_url(filename: str, content_type: str) -> dict[str, str | dict[str, str]]:
    """Generate a presigned B2 upload URL for a single encrypted mod file."""
    storage_key = f"mods/{uuid.uuid4().hex}-{_sanitize_filename(filename)}"
    upload_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.B2_BUCKET_NAME,
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=600,
    )
    file_url = _build_file_url(storage_key)

    return {
        "upload_url": upload_url,
        "file_url": file_url,
        "storage_key": storage_key,
        "method": "PUT",
        "headers": {"Content-Type": content_type},
    }


def head_uploaded_object(storage_key: str) -> dict[str, str | int | None]:
    """Fetch stored object metadata for validation before DB registration."""
    try:
        response = s3_client.head_object(Bucket=settings.B2_BUCKET_NAME, Key=storage_key)
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", "")).strip()
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            raise FileNotFoundError(storage_key) from exc
        raise

    return {
        "content_length": int(response.get("ContentLength") or 0),
        "content_type": response.get("ContentType"),
        "etag": str(response.get("ETag") or "").strip('"'),
    }


def generate_download_url(storage_key: str) -> str:
    """Generate a presigned B2 download URL for a stored encrypted mod."""
    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.B2_BUCKET_NAME,
            "Key": storage_key,
        },
        ExpiresIn=600,
    )
