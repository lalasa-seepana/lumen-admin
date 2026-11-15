from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=120)
    duration_minutes: int = Field(gt=0, le=24 * 60)
    price_paise: Optional[int] = Field(default=None, ge=0)


class ServiceOut(BaseModel):
    id: UUID
    clinic_id: UUID
    name: str
    category: str
    duration_minutes: int
    price_paise: Optional[int] = None
    active: bool
    created_at: datetime
    source_url: Optional[str] = None
    imported_at: Optional[datetime] = None


class AvailabilityCreate(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0=Monday … 6=Sunday")
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)


class AvailabilityOut(BaseModel):
    id: UUID
    clinic_id: UUID
    weekday: int
    start_minute: int
    end_minute: int
    created_at: datetime


class AppointmentCreate(BaseModel):
    customer_id: UUID
    service_id: UUID
    starts_at_utc: datetime


class AppointmentUpdate(BaseModel):
    starts_at_utc: Optional[datetime] = None
    status: Optional[Literal["cancelled"]] = None


class AppointmentOut(BaseModel):
    id: UUID
    clinic_id: UUID
    customer_id: UUID
    customer_name: str
    service_id: UUID
    service_name: str
    starts_at_utc: datetime
    ends_at_utc: datetime
    status: str
    created_at: datetime
    starts_at_clinic: str
    ends_at_clinic: str
    clinic_timezone: str
    voice_session_id: Optional[UUID] = None
    provider: str = "lala"
    sync_status: str = "local"
    external_event_id: Optional[str] = None


class AvailabilityCheckOut(BaseModel):
    available: bool
    reason: Optional[str] = None
    starts_at_utc: datetime
    ends_at_utc: datetime
    clinic_timezone: str
