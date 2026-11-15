from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VisitorSessionCreate(BaseModel):
    clinic_id: Optional[UUID] = None
    clinic_slug: Optional[str] = Field(default=None, max_length=80)
    language: Literal["en-IN", "hi-IN", "te-IN"] = "en-IN"
    recording_consent: bool = False


class VisitorClinicOut(BaseModel):
    id: UUID
    name: str
    public_slug: str
    timezone: str
    ai_disclosure: str = (
        "You are chatting with Rhea, an AI receptionist for this clinic, not a clinician."
    )


class VisitorSessionOut(BaseModel):
    id: UUID
    clinic_id: UUID
    clinic_name: str
    public_slug: str
    language: str
    recording_consent: bool
    status: str
    created_at: datetime
    visitor_token: str
    ws_path: str
    ai_disclosure: str = (
        "You are chatting with Rhea, an AI receptionist for this clinic, not a clinician."
    )