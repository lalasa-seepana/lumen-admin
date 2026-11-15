from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from app.core.config import Settings

ASYMMETRIC_ALGS = {"ES256", "RS256"}
HS_ALGS = {"HS256"}


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    email: Optional[str] = None
    claims: Optional[Dict[str, Any]] = None


@lru_cache(maxsize=8)
def _jwks_client(supabase_url: str) -> PyJWKClient:
    base = supabase_url.rstrip("/")
    return PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json", cache_keys=True)


def _unauthorized(message: str = "Invalid session token", *, code: str = "invalid_token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
    )


def _decode_claims(token: str, settings: Settings) -> Dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise _unauthorized() from exc

    alg = str(header.get("alg") or "")
    decode_options = {"require": ["sub", "exp"]}
    audience = "authenticated"

    try:
        if alg in ASYMMETRIC_ALGS:
            supabase_url = (settings.supabase_url or "").strip()
            if not supabase_url or "YOUR_" in supabase_url:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "auth_unavailable",
                        "message": "Set SUPABASE_URL so Clinic Dial can verify ES256/RS256 session tokens via JWKS",
                    },
                )
            key = _jwks_client(supabase_url).get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                key,
                algorithms=list(ASYMMETRIC_ALGS),
                audience=audience,
                options=decode_options,
            )

        if alg in HS_ALGS:
            secret = (settings.supabase_jwt_secret or "").strip()
            if not secret or "PASTE_" in secret:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"code": "auth_unavailable", "message": "Auth is temporarily unavailable"},
                )
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=audience,
                options=decode_options,
            )

        raise _unauthorized(f"Unsupported session token algorithm: {alg or 'unknown'}")
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Session expired. Please sign in again", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized() from exc


def verify_supabase_jwt(token: str, settings: Settings) -> AuthUser:
    payload = _decode_claims(token, settings)
    sub = payload.get("sub")
    try:
        user_id = UUID(str(sub))
    except (TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    email = payload.get("email")
    return AuthUser(id=user_id, email=str(email) if email else None, claims=payload)
