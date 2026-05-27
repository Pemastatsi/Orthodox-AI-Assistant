"""Envelope encryption for `raw_sensitive_logs.ciphertext`.

ADR-0005 §"Encryption strategy (Phase 1)": AES-256-GCM, data key in Railway secret manager
under `SENSITIVE_LOG_DATA_KEY_BASE64`, multi-version key map keyed by `key_version` so
rotation only needs a deploy with a second env var. Phase 2 migrates to a managed KMS.

`cryptography.hazmat.primitives.ciphers.aead.AESGCM.encrypt()` returns
`ciphertext || auth_tag` as one bytes value; we store that as the `ciphertext` column and
the random 12-byte `nonce` separately. The `key_version` column records which key produced
the row so future rotations can decrypt old rows.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES: int = 12
KEY_BYTES: int = 32


@dataclass(frozen=True)
class EncryptedBlob:
    """Triple persisted on `raw_sensitive_logs`: nonce, ciphertext (incl. tag), key version."""

    nonce: bytes
    ciphertext: bytes
    key_version: str


class CipherKeyError(ValueError):
    pass


class CipherDecryptError(ValueError):
    pass


def load_key_map_from_env(active_b64: str, key_version: str) -> dict[str, bytes]:
    """Phase-1 key map: a single `{key_version: key_bytes}` entry.

    The base64 secret must decode to exactly 32 bytes. Multi-key rotation in a future deploy
    will add more entries here without code changes.
    """
    if not active_b64:
        raise CipherKeyError("SENSITIVE_LOG_DATA_KEY_BASE64 is empty")
    try:
        raw = base64.b64decode(active_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise CipherKeyError(f"SENSITIVE_LOG_DATA_KEY_BASE64 is not valid base64: {exc}") from exc
    if len(raw) != KEY_BYTES:
        raise CipherKeyError(
            f"SENSITIVE_LOG_DATA_KEY_BASE64 decoded to {len(raw)} bytes, expected {KEY_BYTES}"
        )
    return {key_version: raw}


class SensitiveLogCipher:
    """AES-256-GCM cipher with per-row `key_version` so old rows survive rotation."""

    def __init__(self, keys: dict[str, bytes], active_version: str) -> None:
        if active_version not in keys:
            raise CipherKeyError(f"active key_version '{active_version}' not in key map")
        for ver, k in keys.items():
            if len(k) != KEY_BYTES:
                raise CipherKeyError(
                    f"key '{ver}' is {len(k)} bytes; AES-256-GCM requires {KEY_BYTES}"
                )
        self._keys = dict(keys)
        self._active = active_version

    @property
    def active_version(self) -> str:
        return self._active

    def encrypt(self, plaintext: str) -> EncryptedBlob:
        """Encrypt `plaintext` under the active key. Each call generates a fresh nonce."""
        nonce = os.urandom(NONCE_BYTES)
        aesgcm = AESGCM(self._keys[self._active])
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
        return EncryptedBlob(nonce=nonce, ciphertext=ct, key_version=self._active)

    def decrypt(self, blob: EncryptedBlob) -> str:
        """Decrypt `blob` using the key version it was written under.

        Fails closed: unknown key_version or auth-tag mismatch raises `CipherDecryptError`.
        """
        key = self._keys.get(blob.key_version)
        if key is None:
            raise CipherDecryptError(f"unknown key_version '{blob.key_version}'")
        aesgcm = AESGCM(key)
        try:
            pt = aesgcm.decrypt(blob.nonce, blob.ciphertext, associated_data=None)
        except InvalidTag as exc:
            raise CipherDecryptError("authentication tag mismatch") from exc
        return pt.decode("utf-8")


__all__ = [
    "KEY_BYTES",
    "NONCE_BYTES",
    "CipherDecryptError",
    "CipherKeyError",
    "EncryptedBlob",
    "SensitiveLogCipher",
    "load_key_map_from_env",
]
