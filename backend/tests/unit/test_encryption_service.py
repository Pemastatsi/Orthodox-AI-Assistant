"""SensitiveLogCipher: roundtrip, nonce uniqueness, key-version handling."""

from __future__ import annotations

import base64
import os

import pytest
from app.domain.services.encryption_service import (
    KEY_BYTES,
    NONCE_BYTES,
    CipherDecryptError,
    CipherKeyError,
    EncryptedBlob,
    SensitiveLogCipher,
    load_key_map_from_env,
)


def _fresh_cipher(active: str = "v1") -> SensitiveLogCipher:
    return SensitiveLogCipher(keys={active: os.urandom(KEY_BYTES)}, active_version=active)


def test_load_key_map_from_env_decodes_32_bytes() -> None:
    raw = os.urandom(KEY_BYTES)
    b64 = base64.b64encode(raw).decode("ascii")
    keys = load_key_map_from_env(b64, "v1")
    assert keys == {"v1": raw}


@pytest.mark.parametrize(
    "bad_b64,reason",
    [
        ("", "empty"),
        ("not_valid_base64!!!", "base64"),
        (base64.b64encode(b"too_short").decode("ascii"), "expected 32"),
    ],
)
def test_load_key_map_from_env_rejects_bad_input(bad_b64: str, reason: str) -> None:
    with pytest.raises(CipherKeyError, match=reason):
        load_key_map_from_env(bad_b64, "v1")


def test_encrypt_decrypt_roundtrip() -> None:
    cipher = _fresh_cipher()
    plaintext = "What do the fathers teach about prayer?"
    blob = cipher.encrypt(plaintext)
    assert isinstance(blob, EncryptedBlob)
    assert blob.key_version == "v1"
    assert len(blob.nonce) == NONCE_BYTES
    assert cipher.decrypt(blob) == plaintext


def test_encrypt_handles_unicode_greek_and_arabic() -> None:
    cipher = _fresh_cipher()
    plaintext = "τί διδάσκουν οἱ πατέρες; — العربية"
    blob = cipher.encrypt(plaintext)
    assert cipher.decrypt(blob) == plaintext


def test_each_encrypt_generates_unique_nonce() -> None:
    cipher = _fresh_cipher()
    blob_a = cipher.encrypt("hello")
    blob_b = cipher.encrypt("hello")
    assert blob_a.nonce != blob_b.nonce
    assert blob_a.ciphertext != blob_b.ciphertext


def test_ciphertext_includes_auth_tag_layout() -> None:
    """AESGCM.encrypt returns ciphertext || 16-byte tag. Layout invariant."""
    cipher = _fresh_cipher()
    blob = cipher.encrypt("a")
    # Plaintext is 1 byte → ciphertext-with-tag is 1 + 16 = 17 bytes.
    assert len(blob.ciphertext) == 1 + 16


def test_decrypt_unknown_key_version_fails_closed() -> None:
    cipher = _fresh_cipher(active="v1")
    blob = cipher.encrypt("hello")
    bad = EncryptedBlob(nonce=blob.nonce, ciphertext=blob.ciphertext, key_version="v99")
    with pytest.raises(CipherDecryptError, match="unknown key_version"):
        cipher.decrypt(bad)


def test_decrypt_tampered_ciphertext_fails_closed() -> None:
    cipher = _fresh_cipher()
    blob = cipher.encrypt("hello world")
    tampered_ct = bytes([blob.ciphertext[0] ^ 0x01]) + blob.ciphertext[1:]
    tampered = EncryptedBlob(
        nonce=blob.nonce, ciphertext=tampered_ct, key_version=blob.key_version
    )
    with pytest.raises(CipherDecryptError, match="authentication tag"):
        cipher.decrypt(tampered)


def test_decrypt_under_wrong_key_fails_closed() -> None:
    keys = {"v1": os.urandom(KEY_BYTES), "v2": os.urandom(KEY_BYTES)}
    cipher = SensitiveLogCipher(keys=keys, active_version="v1")
    blob = cipher.encrypt("hello")
    # Pretend the row claims v2.
    rebadged = EncryptedBlob(
        nonce=blob.nonce, ciphertext=blob.ciphertext, key_version="v2"
    )
    with pytest.raises(CipherDecryptError, match="authentication tag"):
        cipher.decrypt(rebadged)


def test_multi_key_rotation_old_blobs_still_decrypt() -> None:
    """After rotation, old rows (key_version=v1) decrypt under the v1 key in the map."""
    v1_key = os.urandom(KEY_BYTES)
    v2_key = os.urandom(KEY_BYTES)

    old_cipher = SensitiveLogCipher(keys={"v1": v1_key}, active_version="v1")
    blob = old_cipher.encrypt("old row")

    new_cipher = SensitiveLogCipher(keys={"v1": v1_key, "v2": v2_key}, active_version="v2")
    assert new_cipher.decrypt(blob) == "old row"
    fresh = new_cipher.encrypt("new row")
    assert fresh.key_version == "v2"


def test_active_version_must_be_in_key_map() -> None:
    with pytest.raises(CipherKeyError, match="active key_version"):
        SensitiveLogCipher(keys={"v1": os.urandom(KEY_BYTES)}, active_version="v9")


def test_short_key_rejected() -> None:
    with pytest.raises(CipherKeyError, match="AES-256-GCM"):
        SensitiveLogCipher(keys={"v1": b"too_short"}, active_version="v1")
