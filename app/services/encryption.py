"""Encryption and decryption service."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


class EncryptionService:
    """Service for encrypting/decrypting stored files and launcher payloads."""

    def __init__(self, key: bytes | None = None):
        """Initialize service with Fernet key for at-rest encryption."""
        settings = get_settings()
        self.launcher_salt = settings.LAUNCHER_SALT

        if key is None:
            secret_bytes = settings.MASTER_SECRET.encode("utf-8")
            derived_key = base64.urlsafe_b64encode(
                hashlib.sha256(secret_bytes).digest()
            )
            self.key = derived_key
        else:
            self.key = key

        self.cipher = Fernet(self.key)

    def encrypt_file(self, input_path: str, output_path: str) -> None:
        """Encrypt a file and save to output path."""
        with open(input_path, "rb") as f:
            file_data = f.read()

        encrypted_data = self.cipher.encrypt(file_data)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(encrypted_data)

    def decrypt_file(self, input_path: str, output_path: str) -> None:
        """Decrypt a file and save to output path."""
        with open(input_path, "rb") as f:
            encrypted_data = f.read()

        decrypted_data = self.cipher.decrypt(encrypted_data)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(decrypted_data)

    def encrypt_data(self, data: bytes) -> bytes:
        """Encrypt raw bytes with Fernet (at-rest format)."""
        return self.cipher.encrypt(data)

    def decrypt_data(self, data: bytes) -> bytes:
        """Decrypt raw bytes with Fernet (at-rest format)."""
        return self.cipher.decrypt(data)

    def get_key(self) -> str:
        """Get encryption key as string for storage."""
        return self.key.decode()

    @classmethod
    def from_key_string(cls, key_string: str) -> "EncryptionService":
        """Create service from stored key string."""
        return cls(key=key_string.encode())

    def derive_launcher_key(self, license_key: str, pc_id: str) -> bytes:
        """Derive launcher AES-GCM key using the exact launcher formula."""
        material = (license_key + pc_id + self.launcher_salt).encode("utf-8")
        return hashlib.sha256(material).digest()

    def derive_launcher_key_hex(self, license_key: str, pc_id: str) -> str:
        """Hex view of launcher key for diagnostics/tests."""
        return self.derive_launcher_key(license_key, pc_id).hex()

    def encrypt_for_launcher(
        self,
        plaintext: bytes,
        license_key: str,
        pc_id: str,
        nonce: bytes | None = None,
    ) -> bytes:
        """Encrypt using AES-GCM and return nonce+ciphertext_with_tag."""
        if nonce is None:
            nonce = os.urandom(12)
        if len(nonce) != 12:
            raise ValueError("AES-GCM nonce must be 12 bytes")

        key = self.derive_launcher_key(license_key, pc_id)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt_for_launcher(self, payload: bytes, license_key: str, pc_id: str) -> bytes:
        """Decrypt launcher payload format: nonce(12) + ciphertext_with_tag."""
        if len(payload) < 12 + 16:
            raise ValueError("Payload is too short for nonce + GCM tag")

        nonce = payload[:12]
        ciphertext = payload[12:]

        key = self.derive_launcher_key(license_key, pc_id)
        return AESGCM(key).decrypt(nonce, ciphertext, None)

    def run_launcher_round_trip_self_test(self) -> dict[str, str | int]:
        """Run in-process encrypt/decrypt validation for launcher format."""
        sample_plaintext = b"ets2-round-trip-sample"
        sample_license = "LIC-SELFTEST-001"
        sample_pc = "PC-SELFTEST-001"

        encrypted = self.encrypt_for_launcher(
            sample_plaintext,
            sample_license,
            sample_pc,
        )
        decrypted = self.decrypt_for_launcher(encrypted, sample_license, sample_pc)

        if decrypted != sample_plaintext:
            raise AssertionError("Round-trip decryption mismatch")

        wrong_pc_failed = False
        try:
            self.decrypt_for_launcher(encrypted, sample_license, "PC-SELFTEST-999")
        except InvalidTag:
            wrong_pc_failed = True

        if not wrong_pc_failed:
            raise AssertionError("Wrong PC id did not fail with InvalidTag")

        return {
            "key_hex": self.derive_launcher_key_hex(sample_license, sample_pc),
            "nonce_len": 12,
            "encrypted_len": len(encrypted),
        }
