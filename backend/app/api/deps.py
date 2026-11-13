from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security import AuthUser, verify_supabase_jwt
from app.services.clinic_store import ClinicStore, get_clinic_store


def get_store() -> ClinicStore:
    return get_clinic_store()


def get_bearer_token(authorization: Annotated[Optional[str], Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "missing_token", "message": "Authorization Bearer token required"},
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "missing_token", "message": "Authorization Bearer token required"},
        )
    return token


def get_current_user(
    token: Annotated[str, Depends(get_bearer_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthUser:
    return verify_supabase_jwt(token, settings)


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
StoreDep = Annotated[ClinicStore, Depends(get_store)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
