"""GitHub Releases based storage service for encrypted mod files."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    import requests
except ImportError:  # pragma: no cover - handled via runtime error path
    requests = None

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GitHubStorageError(Exception):
    """Known GitHub storage failure with mapped HTTP semantics."""

    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class GitHubStorageService:
    """Upload encrypted mod files to GitHub Releases assets."""

    def __init__(self) -> None:
        settings = get_settings()
        self.token = settings.GITHUB_STORAGE_TOKEN
        self.api_url = settings.GITHUB_API_URL.rstrip("/")
        self.repo = settings.GITHUB_STORAGE_REPO
        self.owner, self.repo_name = self._parse_repo(self.repo)
        self.timeout = (10, 120)
        if requests is None:
            raise GitHubStorageError(
                "GitHub storage dependency missing: install requests",
                500,
            )

    @staticmethod
    def _parse_repo(repo: str) -> tuple[str, str]:
        parts = repo.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise GitHubStorageError("Invalid GitHub repository configuration", 500)
        return parts[0], parts[1]

    @staticmethod
    def _sanitize_slug(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
        cleaned = cleaned.strip("-._")
        return cleaned or "mod"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @staticmethod
    def _github_error_message(response) -> str:
        """Extract a concise GitHub API error message."""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("message")
                errors = payload.get("errors")
                if errors:
                    return f"{message}; errors={errors}"
                if message:
                    return str(message)
        except ValueError:
            pass
        text = (response.text or "").strip()
        return text[:300] if text else "No response body"

    def create_release(self, tag_name: str, release_name: str) -> dict[str, Any]:
        """Create a release and return JSON body."""
        url = f"{self.api_url}/repos/{self.owner}/{self.repo_name}/releases"
        payload = {
            "tag_name": tag_name,
            "name": release_name,
            "draft": False,
            "prerelease": False,
        }
        try:
            response = requests.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.exception("GitHub release creation request failed")
            raise GitHubStorageError("GitHub storage unavailable", 502) from exc

        if response.status_code in (401, 403):
            logger.error(
                "GitHub auth failure during release create: status=%s detail=%s",
                response.status_code,
                self._github_error_message(response),
            )
            raise GitHubStorageError("GitHub authentication failed", 502)
        if response.status_code == 422:
            failure_detail = self._github_error_message(response)
            logger.error(
                "GitHub release create validation failure: detail=%s",
                failure_detail,
            )
            detail_lower = failure_detail.lower()
            if "repository is empty" in detail_lower:
                raise GitHubStorageError(
                    "GitHub storage repository is empty. Add at least one commit to the repository.",
                    502,
                )
            if "already_exists" in detail_lower or "already exists" in detail_lower:
                raise GitHubStorageError("GitHub release tag already exists", 502)
            raise GitHubStorageError("GitHub release creation failed", 502)
        if not response.ok:
            logger.error(
                "GitHub release create failed: status=%s detail=%s",
                response.status_code,
                self._github_error_message(response),
            )
            raise GitHubStorageError("GitHub storage unavailable", 502)
        return response.json()

    def upload_release_asset(self, release_id: int, file_path: str, filename: str) -> str:
        """Upload one release asset and return browser_download_url."""
        if not filename:
            raise GitHubStorageError("Invalid upload filename", 400)

        upload_url = (
            f"https://uploads.github.com/repos/{self.owner}/{self.repo_name}/"
            f"releases/{release_id}/assets?name={quote(filename)}"
        )
        headers = self._headers()
        headers["Content-Type"] = "application/octet-stream"
        try:
            with open(file_path, "rb") as file_handle:
                response = requests.post(
                    upload_url,
                    headers=headers,
                    data=file_handle,
                    timeout=self.timeout,
                )
        except FileNotFoundError as exc:
            raise GitHubStorageError("Encrypted file not found", 500) from exc
        except requests.RequestException as exc:
            logger.exception("GitHub asset upload request failed")
            raise GitHubStorageError("GitHub storage unavailable", 502) from exc

        if response.status_code in (401, 403):
            logger.error(
                "GitHub auth failure during asset upload: status=%s detail=%s",
                response.status_code,
                self._github_error_message(response),
            )
            raise GitHubStorageError("GitHub authentication failed", 502)
        if not response.ok:
            logger.error(
                "GitHub asset upload failed: status=%s detail=%s",
                response.status_code,
                self._github_error_message(response),
            )
            raise GitHubStorageError("GitHub storage unavailable", 502)

        body = response.json()
        download_url = body.get("browser_download_url")
        if not download_url:
            raise GitHubStorageError("GitHub upload did not return download URL", 502)
        return download_url

    def upload_encrypted_file(self, file_path: str, filename: str) -> str:
        """Create release and upload encrypted file, returning browser URL."""
        if not Path(file_path).exists():
            raise GitHubStorageError("Encrypted file not found", 500)
        if not filename:
            raise GitHubStorageError("Invalid upload filename", 400)

        path = Path(filename)
        stem = path.stem
        parts = stem.rsplit("_", 1)
        mod_name = self._sanitize_slug(parts[0] if parts else stem)
        mod_version = self._sanitize_slug(parts[1] if len(parts) > 1 else "v1")

        base_tag = f"mod-{mod_name}-{mod_version}"
        release_name = f"{mod_name} {mod_version}"

        try:
            release = self.create_release(base_tag, release_name)
        except GitHubStorageError as exc:
            # Retry once with timestamp suffix for tag conflicts.
            if "tag already exists" not in exc.detail.lower():
                raise
            suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            release = self.create_release(f"{base_tag}-{suffix}", release_name)

        release_id = release.get("id")
        if not release_id:
            raise GitHubStorageError("GitHub release creation failed", 502)

        return self.upload_release_asset(int(release_id), file_path, filename)
