from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CalendarConnectionOut(BaseModel):
    provider: Optional[Literal["google", "calcom"]] = None
    status: Literal["connected", "disconnected", "error", "syncing"]
    scheduling_mode: Literal["unset", "lala_only", "google", "calcom"]
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    google_configured: bool
    calcom_configured: bool = False
    google_calendar_id: Optional[str] = None


class SchedulingModeRequest(BaseModel):
    mode: Literal["lala_only", "google", "calcom"]


class GoogleCalendarSelectRequest(BaseModel):
    calendar_id: str = Field(min_length=1)


class CalcomConnectRequest(BaseModel):
    api_key: str = Field(min_length=8)


class CalendarListItem(BaseModel):
    id: str
    summary: Optional[str] = None
    primary: bool = False


class CalendarListOut(BaseModel):
    calendars: List[CalendarListItem]
    selected_calendar_id: Optional[str] = None