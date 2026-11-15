from __future__ import annotations

# Mirrors dashboard calendar-workspace clinic wall-clock helpers (UTC → clinic local).

from datetime import datetime, timezone


def clinic_parts_python(iso: str, tz: str) -> dict[str, str]:
    from zoneinfo import ZoneInfo

    local = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    return {
        "year": f"{local.year:04d}",
        "month": f"{local.month:02d}",
        "day": f"{local.day:02d}",
        "hour": f"{local.hour:02d}",
        "minute": f"{local.minute:02d}",
    }


def test_ist_wall_clock_from_utc():
    parts = clinic_parts_python("2026-12-07T04:30:00+00:00", "Asia/Kolkata")
    assert parts["hour"] == "10"
    assert parts["minute"] == "00"
    assert parts["day"] == "07"