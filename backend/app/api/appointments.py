from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, StoreDep
from app.models.appointments import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    AvailabilityCheckOut,
    AvailabilityCreate,
    AvailabilityOut,
    ServiceCreate,
    ServiceOut,
)
from app.services import appointments as appointment_service

router = APIRouter(prefix="/v1", tags=["appointments"])


@router.get("/services", response_model=List[ServiceOut])
def get_services(user: CurrentUser, store: StoreDep) -> List[ServiceOut]:
    return appointment_service.list_services(store, user_id=user.id)


@router.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def post_service(body: ServiceCreate, user: CurrentUser, store: StoreDep) -> ServiceOut:
    return appointment_service.create_service(
        store,
        user_id=user.id,
        name=body.name,
        category=body.category,
        duration_minutes=body.duration_minutes,
        price_paise=body.price_paise,
    )


@router.get("/availability", response_model=List[AvailabilityOut])
def get_availability(user: CurrentUser, store: StoreDep) -> List[AvailabilityOut]:
    return appointment_service.list_availability(store, user_id=user.id)


@router.post("/availability", response_model=AvailabilityOut, status_code=status.HTTP_201_CREATED)
def post_availability(
    body: AvailabilityCreate, user: CurrentUser, store: StoreDep
) -> AvailabilityOut:
    return appointment_service.add_availability(
        store,
        user_id=user.id,
        weekday=body.weekday,
        start_minute=body.start_minute,
        end_minute=body.end_minute,
    )


@router.get("/availability/check", response_model=AvailabilityCheckOut)
def check_availability(
    user: CurrentUser,
    store: StoreDep,
    service_id: UUID = Query(...),
    starts_at_utc: str = Query(...),
) -> AvailabilityCheckOut:
    from datetime import datetime

    starts = datetime.fromisoformat(starts_at_utc.replace("Z", "+00:00"))
    return appointment_service.check_slot(
        store, user_id=user.id, service_id=service_id, starts_at_utc=starts
    )


@router.get("/appointments", response_model=List[AppointmentOut])
def get_appointments(user: CurrentUser, store: StoreDep) -> List[AppointmentOut]:
    return appointment_service.list_appointments(store, user_id=user.id)


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def post_appointment(
    body: AppointmentCreate, user: CurrentUser, store: StoreDep
) -> AppointmentOut:
    return appointment_service.create_appointment(
        store,
        user_id=user.id,
        customer_id=body.customer_id,
        service_id=body.service_id,
        starts_at_utc=body.starts_at_utc,
    )


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def patch_appointment(
    appointment_id: UUID, body: AppointmentUpdate, user: CurrentUser, store: StoreDep
) -> AppointmentOut:
    return appointment_service.update_appointment(
        store,
        user_id=user.id,
        appointment_id=appointment_id,
        starts_at_utc=body.starts_at_utc,
        status_value=body.status,
    )
