from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass


KEY_PREFIX_TAG = "lala_live"


@dataclass(frozen=True)
class GeneratedIntegrationKey:
    plaintext: str
    key_hash: str
    key_prefix: str


def hash_integration_key(plaintext: str, pepper: str) -> str:
    """SHA-256(HMAC) of the key using server pepper. Never store plaintext."""
    material = plaintext.strip().encode("utf-8")
    pepper_bytes = pepper.encode("utf-8")
    return hmac.new(pepper_bytes, material, hashlib.sha256).hexdigest()


def generate_integration_key(pepper: str) -> GeneratedIntegrationKey:
    """Mint a one-time plaintext key. Caller must show it once and store hash + prefix only."""
    if len(pepper.strip()) < 16:
        raise ValueError("pepper_too_short")
    public_prefix = secrets.token_hex(4)  # 8 hex chars
    secret = secrets.token_urlsafe(24)
    plaintext = f"{KEY_PREFIX_TAG}_{public_prefix}_{secret}"
    return GeneratedIntegrationKey(
        plaintext=plaintext,
        key_hash=hash_integration_key(plaintext, pepper),
        key_prefix=public_prefix,
    )


def keys_equal(left_hash: str, right_hash: str) -> bool:
    return hmac.compare_digest(left_hash, right_hash)
