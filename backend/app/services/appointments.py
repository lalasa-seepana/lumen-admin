from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.appointments import (
    AppointmentOut,
    AvailabilityCheckOut,
    AvailabilityOut,
    ServiceOut,
)
from app.services import clinics as clinic_service
from app.services import onboarding as onboarding_service
from app.services.booking_rules import within_availability
from app.services.calcom_sync import sync_appointment_to_calcom
from app.services.clinic_store import ClinicStore


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def _clinic_stamp(dt: datetime, tz_name: str) -> str:
    local = dt.astimezone(_tz(tz_name))
    return local.strftime("%Y-%m-%d %H:%M %Z")


def _service_out(row) -> ServiceOut:
    return ServiceOut(
        id=row.id,
        clinic_id=row.clinic_id,
        name=row.name,
        category=row.category,
        duration_minutes=row.duration_minutes,
        price_paise=row.price_paise,
        active=row.active,
        created_at=row.created_at,
        source_url=getattr(row, "source_url", None),
        imported_at=getattr(row, "imported_at", None),
    )


def _availability_out(row) -> AvailabilityOut:
    return AvailabilityOut(
        id=row.id,
        clinic_id=row.clinic_id,
        weekday=row.weekday,
        start_minute=row.start_minute,
        end_minute=row.end_minute,
        created_at=row.created_at,
    )


def _appointment_out(store: ClinicStore, clinic, row) -> AppointmentOut:
    customer = store.get_customer(clinic.id, row.customer_id)
    service = store.get_service(clinic.id, row.service_id)
    return AppointmentOut(
        id=row.id,
        clinic_id=row.clinic_id,
        customer_id=row.customer_id,
        customer_name=customer.full_name if customer else "Unknown",
        service_id=row.service_id,
        service_name=service.name if service else "Unknown",
        starts_at_utc=row.starts_at_utc,
        ends_at_utc=row.ends_at_utc,
        status=row.status,
        created_at=row.created_at,
        starts_at_clinic=_clinic_stamp(row.starts_at_utc, clinic.timezone),
        ends_at_clinic=_clinic_stamp(row.ends_at_utc, clinic.timezone),
        clinic_timezone=clinic.timezone,
        voice_session_id=getattr(row, "voice_session_id", None),
        provider=getattr(row, "provider", None) or "lala",
        sync_status=getattr(row, "sync_status", None) or "local",
        external_event_id=getattr(row, "external_event_id", None),
    )


def list_services(store: ClinicStore, *, user_id: UUID) -> List[ServiceOut]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return [_service_out(row) for row in store.list_services(clinic.id, active_only=False)]


def create_service(
    store: ClinicStore,
    *,
    user_id: UUID,
    name: str,
    category: str,
    duration_minutes: int,
    price_paise: Optional[int],
) -> ServiceOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    row = store.create_service(
        clinic_id=clinic.id,
        name=name.strip(),
        category=category.strip(),
        duration_minutes=duration_minutes,
        price_paise=price_paise,
    )
    store.add_activity_event(
        clinic_id=clinic.id,
        actor_type="owner",
        action="service.created",
        entity_type="service",
        entity_id=row.id,
        payload={"name": row.name},
    )
    return _service_out(row)


def list_availability(store: ClinicStore, *, user_id: UUID) -> List[AvailabilityOut]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return [_availability_out(row) for row in store.list_availability(clinic.id)]


def add_availability(
    store: ClinicStore, *, user_id: UUID, weekday: int, start_minute: int, end_minute: int
) -> AvailabilityOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    if end_minute <= start_minute:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_window", "message": "end_minute must be after start_minute"},
        )
    row = store.add_availability_window(
        clinic_id=clinic.id,
        weekday=weekday,
        start_minute=start_minute,
        end_minute=end_minute,
    )
    onboarding_service.complete_step_if_hours_present(store, clinic.id)
    store.add_activity_event(
        clinic_id=clinic.id,
        actor_type="owner",
        action="availability.created",
        entity_type="availability_window",
        entity_id=row.id,
        payload={"weekday": weekday, "start_minute": start_minute, "end_minute": end_minute},
    )
    return _availability_out(row)


def list_appointments(store: ClinicStore, *, user_id: UUID) -> List[AppointmentOut]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return [
        _appointment_out(store, clinic, row)
        for row in store.list_appointments(clinic.id, include_cancelled=True)
    ]


def check_slot(
    store: ClinicStore, *, user_id: UUID, service_id: UUID, starts_at_utc: datetime
) -> AvailabilityCheckOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    starts = starts_at_utc.astimezone(timezone.utc) if starts_at_utc.tzinfo else starts_at_utc.replace(
        tzinfo=timezone.utc
    )
    service = store.get_service(clinic.id, service_id)
    if service is None or not service.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "service_not_found", "message": "Service not found"},
        )
    ends = starts + timedelta(minutes=service.duration_minutes)
    if not within_availability(store, clinic.id, starts, ends, clinic.timezone):
        return AvailabilityCheckOut(
            available=False,
            reason="outside_availability",
            starts_at_utc=starts,
            ends_at_utc=ends,
            clinic_timezone=clinic.timezone,
        )
    for existing in store.list_appointments(clinic.id, include_cancelled=False):
        if starts < existing.ends_at_utc and ends > existing.starts_at_utc:
            return AvailabilityCheckOut(
                available=False,
                reason="appointment_conflict",
                starts_at_utc=starts,
                ends_at_utc=ends,
                clinic_timezone=clinic.timezone,
            )
    return AvailabilityCheckOut(
        available=True,
        reason=None,
        starts_at_utc=starts,
        ends_at_utc=ends,
        clinic_timezone=clinic.timezone,
    )


def create_appointment(
    store: ClinicStore,
    *,
    user_id: UUID,
    customer_id: UUID,
    service_id: UUID,
    starts_at_utc: datetime,
) -> AppointmentOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    starts = starts_at_utc.astimezone(timezone.utc) if starts_at_utc.tzinfo else starts_at_utc.replace(
        tzinfo=timezone.utc
    )
    customer = store.get_customer(clinic.id, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "customer_not_found", "message": "Customer not found"},
        )
    service = store.get_service(clinic.id, service_id)
    if service is None or not service.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "service_not_found", "message": "Service not found"},
        )
    ends = starts + timedelta(minutes=service.duration_minutes)
    if not within_availability(store, clinic.id, starts, ends, clinic.timezone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "outside_availability", "message": "Slot is outside clinic availability"},
        )
    clinic_record = store.get_clinic(clinic.id)
    scheduling_mode = clinic_record.scheduling_mode if clinic_record else "unset"
    provider = "lala"
    sync_status = "local"
    if scheduling_mode == "calcom":
        provider = "calcom"
        sync_status = "pending_provider"
    try:
        row = store.create_appointment(
            clinic_id=clinic.id,
            customer_id=customer_id,
            service_id=service_id,
            starts_at_utc=starts,
            ends_at_utc=ends,
            provider=provider,
            sync_status=sync_status,
        )
    except ValueError as exc:
        if str(exc) == "appointment_conflict":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "appointment_conflict", "message": "Overlapping appointment exists"},
            ) from exc
        raise
    if scheduling_mode == "calcom":
        sync_appointment_to_calcom(
            store, get_settings(), clinic_id=clinic.id, appointment_id=row.id
        )
        refreshed = store.get_appointment(clinic.id, row.id)
        if refreshed is not None:
            row = refreshed
    store.add_activity_event(
        clinic_id=clinic.id,
        actor_type="owner",
        action="appointment.created",
        entity_type="appointment",
        entity_id=row.id,
        payload={
            "customer_id": str(customer_id),
            "service_id": str(service_id),
            "provider": row.provider,
            "sync_status": row.sync_status,
            "external_event_id": row.external_event_id,
        },
    )
    return _appointment_out(store, clinic, row)


def update_appointment(
    store: ClinicStore,
    *,
    user_id: UUID,
    appointment_id: UUID,
    starts_at_utc: Optional[datetime],
    status_value: Optional[str],
) -> AppointmentOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    existing = store.get_appointment(clinic.id, appointment_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "appointment_not_found", "message": "Appointment not found"},
        )

    if status_value == "cancelled":
        row = store.cancel_appointment(clinic_id=clinic.id, appointment_id=appointment_id)
        store.add_activity_event(
            clinic_id=clinic.id,
            actor_type="owner",
            action="appointment.cancelled",
            entity_type="appointment",
            entity_id=row.id,
            payload={},
        )
        return _appointment_out(store, clinic, row)

    if starts_at_utc is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_update", "message": "Provide starts_at_utc or status=cancelled"},
        )

    starts = starts_at_utc.astimezone(timezone.utc) if starts_at_utc.tzinfo else starts_at_utc.replace(
        tzinfo=timezone.utc
    )
    service = store.get_service(clinic.id, existing.service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "service_not_found", "message": "Service not found"},
        )
    ends = starts + timedelta(minutes=service.duration_minutes)
    if not within_availability(store, clinic.id, starts, ends, clinic.timezone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "outside_availability", "message": "Slot is outside clinic availability"},
        )
    try:
        row = store.reschedule_appointment(
            clinic_id=clinic.id,
            appointment_id=appointment_id,
            starts_at_utc=starts,
            ends_at_utc=ends,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "appointment_conflict":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "appointment_conflict", "message": "Overlapping appointment exists"},
            ) from exc
        if code in {"appointment_not_found", "appointment_cancelled"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": code, "message": "Appointment not found or cancelled"},
            ) from exc
        raise
    store.add_activity_event(
        clinic_id=clinic.id,
        actor_type="owner",
        action="appointment.rescheduled",
        entity_type="appointment",
        entity_id=row.id,
        payload={"starts_at_utc": starts.isoformat()},
    )
    return _appointment_out(store, clinic, row)
