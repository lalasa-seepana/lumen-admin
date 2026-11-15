from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.appointments import AppointmentOut


class ConversationTurnOut(BaseModel):
    id: UUID
    sequence: int
    role: Literal["user", "assistant", "system"]
    text: str
    has_audio_blob: bool
    created_at: datetime


class ConversationListItem(BaseModel):
    id: UUID
    clinic_id: UUID
    voice_session_id: UUID
    language: str
    recording_consent: bool
    transcript_available: bool
    retention_until: datetime
    deleted_at: Optional[datetime] = None
    turn_count: int = 0
    handover_count: int = 0
    appointment_count: int = 0
    created_at: datetime
    closed_at: Optional[datetime] = None


class ConversationDetail(ConversationListItem):
    turns: List[ConversationTurnOut] = Field(default_factory=list)
    appointments: List[AppointmentOut] = Field(default_factory=list)
    retention_note: str = (
        "Transcripts and recording metadata are retained for the clinic retention window, "
        "then hard-deleted. Audio blobs are never stored without recording consent."
    )


class HandoverUpdate(BaseModel):
    status: Literal["open", "acked", "closed"]


class RetentionPurgeResult(BaseModel):
    retention_days: int
    conversations_purged: int
    turns_purged: int
    cutoff: datetime
