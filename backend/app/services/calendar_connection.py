from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings
from app.models.calendar_providers import (
    CalcomConnectRequest,
    CalendarConnectionOut,
    CalendarListOut,
    GoogleCalendarSelectRequest,
    SchedulingModeRequest,
)
from app.services import clinics as clinic_service
from app.services.clinic_store import ClinicStore
from app.services.integration_crypto import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

_CALCOM_API = "https://api.cal.com/v2"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def _google_connected(record) -> bool:
    return bool(record.google_refresh_token_enc and not record.google_refresh_token_enc.startswith("stub:"))


def _connection_out(store: ClinicStore, settings: Settings, clinic_id: UUID) -> CalendarConnectionOut:
    record = store.get_clinic(clinic_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "clinic_not_found"})
    calcom = store.get_calendar_provider_connection(clinic_id, "calcom")
    provider: Optional[str] = None
    conn_status = record.google_status or "disconnected"
    if record.scheduling_mode == "google" and _google_connected(record):
        provider = "google"
        conn_status = "connected"
    elif record.scheduling_mode == "calcom" and calcom and calcom.status == "connected":
        provider = "calcom"
        conn_status = calcom.status
    return CalendarConnectionOut(
        provider=provider,
        status=conn_status,
        scheduling_mode=record.scheduling_mode,
        last_sync_at=record.google_last_sync_at or (calcom.last_sync_at if calcom else None),
        last_error=record.google_last_error or (calcom.last_error if calcom else None),
        google_configured=settings.google_calendar_configured,
        calcom_configured=settings.calcom_configured,
        google_calendar_id=record.google_calendar_id,
    )


def get_connection(store: ClinicStore, settings: Settings, *, user_id: UUID) -> CalendarConnectionOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return _connection_out(store, settings, clinic.id)


def set_scheduling_mode(
    store: ClinicStore, settings: Settings, *, user_id: UUID, body: SchedulingModeRequest
) -> CalendarConnectionOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    if body.mode == "google" and not settings.google_calendar_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "google_not_configured", "message": "Google OAuth credentials are not set"},
        )
    if body.mode == "calcom":
        calcom = store.get_calendar_provider_connection(clinic.id, "calcom")
        if calcom is None or calcom.status != "connected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "calcom_not_connected", "message": "Connect Cal.com with an API key first"},
            )
    store.update_clinic(
        clinic.id,
        scheduling_mode=body.mode,
        google_status="disconnected" if body.mode in {"lala_only", "calcom"} else clinic.google_status,
    )
    store.upsert_onboarding_step(clinic_id=clinic.id, step_key="calendar_choice", status="completed")
    return _connection_out(store, settings, clinic.id)


def start_google_oauth(store: ClinicStore, settings: Settings, *, user_id: UUID) -> dict:
    clinic, _ = clinic_service.require_membership(store, user_id)
    if not settings.google_calendar_configured:
        return {
            "authorize_url": None,
            "code": "google_not_configured",
            "message": "Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to connect Google Calendar.",
        }
    state = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    store.save_oauth_state(
        state=state,
        clinic_id=clinic.id,
        user_id=user_id,
        provider="google",
        expires_at=expires,
    )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    from urllib.parse import urlencode

    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"authorize_url": url}


def _exchange_google_code(settings: Settings, code: str) -> dict:
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code != 200:
        logger.warning("google token exchange failed: %s", response.text[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "google_token_exchange_failed", "message": "Could not exchange OAuth code"},
        )
    return response.json()


def _google_access_token(settings: Settings, refresh_token_enc: str) -> str:
    pepper = settings.lala_integration_key_pepper
    if not pepper.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "encryption_not_configured", "message": "LALA_INTEGRATION_KEY_PEPPER is required"},
        )
    refresh_token = decrypt_secret(pepper, refresh_token_enc)
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "google_refresh_failed", "message": "Could not refresh Google access token"},
        )
    body = response.json()
    token = body.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "google_refresh_failed", "message": "No access token in Google response"},
        )
    return token


def google_oauth_callback(store: ClinicStore, settings: Settings, *, code: str, state: str) -> dict:
    if not settings.google_calendar_configured:
        return {"status": "not_configured", "message": "Google OAuth is not configured on this server"}
    if not code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "missing_code", "message": "Authorization code is required"},
        )
    oauth = store.take_oauth_state(state)
    if oauth is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_state"})
    if oauth.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "expired_state"})
    clinic = store.get_clinic(oauth.clinic_id)
    if clinic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "clinic_not_found"})
    token_body = _exchange_google_code(settings, code)
    refresh = token_body.get("refresh_token")
    if not refresh:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "no_refresh_token",
                "message": "Google did not return a refresh token; revoke app access and retry with prompt=consent",
            },
        )
    pepper = settings.lala_integration_key_pepper
    if not pepper.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "encryption_not_configured", "message": "LALA_INTEGRATION_KEY_PEPPER is required"},
        )
    enc = encrypt_secret(pepper, refresh)
    store.update_clinic(
        oauth.clinic_id,
        google_refresh_token_enc=enc,
        google_status="connected",
        scheduling_mode="google",
        google_last_error=None,
    )
    store.upsert_onboarding_step(clinic_id=oauth.clinic_id, step_key="calendar_choice", status="completed")
    return {"status": "connected", "clinic_id": str(oauth.clinic_id)}


def disconnect_google(store: ClinicStore, settings: Settings, *, user_id: UUID) -> CalendarConnectionOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    store.update_clinic(
        clinic.id,
        google_refresh_token_enc=None,
        google_calendar_id=None,
        google_status="disconnected",
        google_last_error=None,
        scheduling_mode="lala_only" if clinic.scheduling_mode == "google" else clinic.scheduling_mode,
    )
    return _connection_out(store, settings, clinic.id)


def list_google_calendars(store: ClinicStore, settings: Settings, *, user_id: UUID) -> CalendarListOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    if not settings.google_calendar_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "google_not_configured"},
        )
    if not _google_connected(clinic):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "google_not_connected"},
        )
    access = _google_access_token(settings, clinic.google_refresh_token_enc or "")
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            f"{_GOOGLE_CALENDAR_API}/users/me/calendarList",
            headers={"Authorization": f"Bearer {access}"},
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "google_calendar_list_failed"},
        )
    items = response.json().get("items", [])
    calendars = [
        {
            "id": item.get("id"),
            "summary": item.get("summary"),
            "primary": bool(item.get("primary")),
        }
        for item in items
        if item.get("id")
    ]
    return CalendarListOut(calendars=calendars, selected_calendar_id=clinic.google_calendar_id)


def select_google_calendar(
    store: ClinicStore, settings: Settings, *, user_id: UUID, body: GoogleCalendarSelectRequest
) -> CalendarConnectionOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    if not _google_connected(clinic):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "google_not_connected"})
    store.update_clinic(clinic.id, google_calendar_id=body.calendar_id)
    return _connection_out(store, settings, clinic.id)


def check_external_busy(
    store: ClinicStore, settings: Settings, *, clinic_id: UUID, starts_at_utc: datetime, ends_at_utc: datetime
) -> dict:
    """Returns unavailable when a connected provider times out (conservative block)."""
    clinic = store.get_clinic(clinic_id)
    if clinic is None:
        return {"available": True, "reason": None}
    if clinic.scheduling_mode == "google" and _google_connected(clinic):
        cal_id = clinic.google_calendar_id or "primary"
        try:
            access = _google_access_token(settings, clinic.google_refresh_token_enc or "")
            params = {
                "timeMin": starts_at_utc.isoformat().replace("+00:00", "Z"),
                "timeMax": ends_at_utc.isoformat().replace("+00:00", "Z"),
                "items": [{"id": cal_id}],
            }
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    f"{_GOOGLE_CALENDAR_API}/freeBusy",
                    headers={"Authorization": f"Bearer {access}"},
                    json=params,
                )
            if response.status_code != 200:
                return {"available": False, "reason": "google_busy_check_failed"}
            busy = response.json().get("calendars", {}).get(cal_id, {}).get("busy", [])
            if busy:
                return {"available": False, "reason": "google_busy"}
        except httpx.TimeoutException:
            return {"available": False, "reason": "google_busy_timeout"}
        except HTTPException:
            return {"available": False, "reason": "google_busy_error"}
    return {"available": True, "reason": None}


async def connect_calcom(
    store: ClinicStore, settings: Settings, *, user_id: UUID, body: CalcomConnectRequest
) -> CalendarConnectionOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "missing_api_key"})
    headers = {"Authorization": f"Bearer {api_key}", "cal-api-version": "2024-08-13"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{_CALCOM_API}/me", headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": "calcom_timeout", "message": "Cal.com API did not respond in time"},
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "calcom_invalid_key",
                "message": "Cal.com rejected this API key — live verification requires valid credentials",
            },
        )
    pepper = settings.lala_integration_key_pepper
    if not pepper.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "encryption_not_configured"},
        )
    enc = encrypt_secret(pepper, api_key)
    webhook_secret = settings.calcom_webhook_secret.strip() or secrets.token_urlsafe(24)
    from app.services.calcom_sync import fetch_event_types_async

    event_types = await fetch_event_types_async(api_key)
    me_data = response.json().get("data") or {}
    config: dict[str, Any] = {
        "username": me_data.get("username"),
        "event_types": event_types,
    }
    if event_types:
        config["default_event_type_id"] = event_types[0]["id"]
    last_error = None if event_types else "Connected, but no Cal.com event types were found to book against"
    store.upsert_calendar_provider_connection(
        clinic_id=clinic.id,
        provider="calcom",
        api_key_enc=enc,
        status="connected",
        last_sync_at=datetime.now(timezone.utc),
        last_error=last_error,
        config=config,
        webhook_secret=webhook_secret,
    )
    if clinic.scheduling_mode in {"unset", "lala_only"}:
        store.update_clinic(clinic.id, scheduling_mode="calcom")
        store.upsert_onboarding_step(clinic_id=clinic.id, step_key="calendar_choice", status="completed")
    return _connection_out(store, settings, clinic.id)


def disconnect_calcom(store: ClinicStore, settings: Settings, *, user_id: UUID) -> CalendarConnectionOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    store.upsert_calendar_provider_connection(
        clinic_id=clinic.id,
        provider="calcom",
        api_key_enc=None,
        status="disconnected",
        last_error=None,
    )
    if clinic.scheduling_mode == "calcom":
        store.update_clinic(clinic.id, scheduling_mode="lala_only")
    return _connection_out(store, settings, clinic.id)


_webhook_delivery_keys: set[str] = set()


def verify_calcom_webhook(settings: Settings, *, signature: str, body: bytes, clinic_id: UUID) -> bool:
    secret = settings.calcom_webhook_secret.strip()
    if not secret:
        logger.warning("CALCOM_WEBHOOK_SECRET not set — webhook signature verification disabled")
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def handle_calcom_webhook(
    store: ClinicStore,
    settings: Settings,
    *,
    clinic_id: UUID,
    delivery_id: str,
    payload: dict,
) -> dict:
    """Idempotent webhook handler scaffold — extend when Cal.com event mapping is wired."""
    if delivery_id in _webhook_delivery_keys:
        return {"status": "duplicate", "delivery_id": delivery_id}
    _webhook_delivery_keys.add(delivery_id)
    existing = store.get_calendar_provider_connection(clinic_id, "calcom")
    config = dict(existing.config) if existing and existing.config else {}
    config["last_webhook"] = payload.get("triggerEvent")
    store.upsert_calendar_provider_connection(
        clinic_id=clinic_id,
        provider="calcom",
        status="connected",
        last_sync_at=datetime.now(timezone.utc),
        last_error=None,
        config=config,
    )
    return {"status": "accepted", "delivery_id": delivery_id}