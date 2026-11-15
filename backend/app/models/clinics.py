from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ClinicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    timezone: Optional[str] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Clinic name must be at least 2 characters")
        return cleaned


class ClinicOut(BaseModel):
    id: UUID
    name: str
    timezone: str
    created_at: datetime
    public_slug: str = ""


class MembershipOut(BaseModel):
    clinic_id: UUID
    user_id: UUID
    role: Literal["owner"]


class MeOut(BaseModel):
    user_id: UUID
    email: Optional[str] = None
    clinic: Optional[ClinicOut] = None
    membership: Optional[MembershipOut] = None
