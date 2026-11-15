from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.services.clinic_store import ClinicStore


def _clinic_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def within_availability(
    store: ClinicStore,
    clinic_id: UUID,
    starts: datetime,
    ends: datetime,
    clinic_timezone: str,
) -> bool:
    """True if the UTC range sits inside a clinic availability window (local clinic time)."""
    windows = store.list_availability(clinic_id)
    if not windows:
        return False
    tz = _clinic_tz(clinic_timezone)
    local_start = starts.astimezone(tz)
    local_end = ends.astimezone(tz)
    if local_end.date() != local_start.date():
        return False
    weekday = local_start.weekday()
    start_minute = local_start.hour * 60 + local_start.minute
    end_minute = local_end.hour * 60 + local_end.minute
    for window in windows:
        if (
            window.weekday == weekday
            and start_minute >= window.start_minute
            and end_minute <= window.end_minute
        ):
            return True
    return False