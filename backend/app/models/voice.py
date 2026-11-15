from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VoiceSessionCreate(BaseModel):
    language: Literal["en-IN", "hi-IN", "te-IN"] = "en-IN"
    recording_consent: bool = False


class VoiceSessionOut(BaseModel):
    id: UUID
    clinic_id: UUID
    language: str
    recording_consent: bool
    status: str
    created_at: datetime
    visitor_token: Optional[str] = None
    ws_path: str = Field(description="Relative WebSocket path including session id")


class HandoverOut(BaseModel):
    id: UUID
    clinic_id: UUID
    voice_session_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    reason: str
    summary: str
    status: str
    created_at: datetime
    callback_contact: Optional[str] = None
