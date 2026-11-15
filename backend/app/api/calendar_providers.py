from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, Query, Request

from app.api.deps import CurrentUser, SettingsDep, StoreDep
from app.models.calendar_providers import (
    CalcomConnectRequest,
    CalendarConnectionOut,
    CalendarListOut,
    GoogleCalendarSelectRequest,
    SchedulingModeRequest,
)
from app.services import calendar_connection as calendar_service

router = APIRouter(prefix="/v1/calendar", tags=["calendar"])


@router.get("/connection", response_model=CalendarConnectionOut)
def calendar_connection(user: CurrentUser, store: StoreDep, settings: SettingsDep) -> CalendarConnectionOut:
    return calendar_service.get_connection(store, settings, user_id=user.id)


@router.post("/scheduling-mode", response_model=CalendarConnectionOut)
def scheduling_mode(
    body: SchedulingModeRequest, user: CurrentUser, store: StoreDep, settings: SettingsDep
) -> CalendarConnectionOut:
    return calendar_service.set_scheduling_mode(store, settings, user_id=user.id, body=body)


@router.post("/google/authorize")
def google_authorize(user: CurrentUser, store: StoreDep, settings: SettingsDep) -> dict:
    return calendar_service.start_google_oauth(store, settings, user_id=user.id)


@router.get("/google/callback")
def google_callback(
    store: StoreDep,
    settings: SettingsDep,
    code: str = Query(default=""),
    state: str = Query(default=""),
) -> dict:
    return calendar_service.google_oauth_callback(store, settings, code=code, state=state)


@router.post("/google/disconnect", response_model=CalendarConnectionOut)
def google_disconnect(user: CurrentUser, store: StoreDep, settings: SettingsDep) -> CalendarConnectionOut:
    return calendar_service.disconnect_google(store, settings, user_id=user.id)


@router.get("/google/calendars", response_model=CalendarListOut)
def google_calendars(user: CurrentUser, store: StoreDep, settings: SettingsDep) -> CalendarListOut:
    return calendar_service.list_google_calendars(store, settings, user_id=user.id)


@router.post("/google/calendar", response_model=CalendarConnectionOut)
def google_select_calendar(
    body: GoogleCalendarSelectRequest, user: CurrentUser, store: StoreDep, settings: SettingsDep
) -> CalendarConnectionOut:
    return calendar_service.select_google_calendar(store, settings, user_id=user.id, body=body)


@router.post("/calcom/connect", response_model=CalendarConnectionOut)
async def calcom_connect(
    body: CalcomConnectRequest, user: CurrentUser, store: StoreDep, settings: SettingsDep
) -> CalendarConnectionOut:
    return await calendar_service.connect_calcom(store, settings, user_id=user.id, body=body)


@router.post("/calcom/disconnect", response_model=CalendarConnectionOut)
def calcom_disconnect(user: CurrentUser, store: StoreDep, settings: SettingsDep) -> CalendarConnectionOut:
    return calendar_service.disconnect_calcom(store, settings, user_id=user.id)


@router.post("/calcom/webhook/{clinic_id}")
async def calcom_webhook(
    clinic_id: UUID,
    request: Request,
    store: StoreDep,
    settings: SettingsDep,
    x_cal_signature_256: str = Header(default=""),
    x_cal_delivery_id: str = Header(default=""),
) -> dict:
    import json

    body = await request.body()
    if settings.calcom_webhook_secret.strip():
        if not calendar_service.verify_calcom_webhook(
            settings, signature=x_cal_signature_256, body=body, clinic_id=clinic_id
        ):
            return {"status": "rejected", "reason": "invalid_signature"}
    payload = json.loads(body.decode("utf-8") if body else "{}")
    delivery_id = x_cal_delivery_id or payload.get("id") or ""
    return calendar_service.handle_calcom_webhook(
        store, settings, clinic_id=clinic_id, delivery_id=str(delivery_id), payload=payload
    )