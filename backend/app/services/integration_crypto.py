from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def fernet_from_pepper(pepper: str) -> Fernet:
    if not pepper.strip():
        raise ValueError("encryption_pepper_missing")
    digest = hashlib.sha256(pepper.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(pepper: str, plaintext: str) -> str:
    token = fernet_from_pepper(pepper).encrypt(plaintext.encode("utf-8"))
    return f"enc:{token.decode('ascii')}"


def decrypt_secret(pepper: str, stored: str) -> str:
    if not stored.startswith("enc:"):
        raise ValueError("secret_not_encrypted")
    try:
        raw = fernet_from_pepper(pepper).decrypt(stored[4:].encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("secret_decrypt_failed") from exc
    return raw.decode("utf-8")