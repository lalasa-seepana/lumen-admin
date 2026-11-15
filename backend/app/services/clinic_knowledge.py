"""Approved clinic facts for the receptionist (RAG-lite, no vectors yet).

Only owner-backed records: clinic profile, active services, opening hours.
Unknown topics must go through escalate — never invent.
"""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from app.services.clinic_store import ClinicStore

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _format_minutes(minute: int) -> str:
    hour, mins = divmod(int(minute), 60)
    return f"{hour:02d}:{mins:02d}"


def build_clinic_knowledge(store: ClinicStore, clinic_id: UUID) -> Dict[str, Any]:
    clinic = store.get_clinic(clinic_id)
    if clinic is None:
        return {
            "clinic_id": str(clinic_id),
            "found": False,
            "instruction": "Clinic not found. Escalate to staff.",
        }

    services = []
    for row in store.list_services(clinic_id, active_only=True):
        price = None
        if row.price_paise is not None:
            currency = getattr(row, "currency", None) or "INR"
            price = {
                "amount": row.price_paise / 100.0,
                "currency": currency,
                "display": f"{currency} {row.price_paise / 100.0:.2f}",
            }
        services.append(
            {
                "id": str(row.id),
                "name": row.name,
                "category": row.category,
                "duration_minutes": row.duration_minutes,
                "price": price,
            }
        )

    hours: List[Dict[str, Any]] = []
    for window in store.list_availability(clinic_id):
        day = _WEEKDAYS[window.weekday] if 0 <= window.weekday < 7 else str(window.weekday)
        hours.append(
            {
                "weekday": window.weekday,
                "day": day,
                "open": _format_minutes(window.start_minute),
                "close": _format_minutes(window.end_minute),
                "clinic_local": True,
            }
        )

    return {
        "found": True,
        "clinic_id": str(clinic.id),
        "name": clinic.name,
        "timezone": clinic.timezone,
        "website_url": clinic.website_url,
        "scheduling_mode": clinic.scheduling_mode,
        "services": services,
        "opening_hours": hours,
        "approved_faqs": [],
        "instruction": (
            "Answer ONLY from these approved facts. "
            "If the visitor asks something missing here, say you do not have that on file "
            "and call escalate. Never invent prices, hours, policies, or medical advice."
        ),
    }


def clinic_knowledge_prompt_block(store: ClinicStore, clinic_id: UUID) -> str:
    data = build_clinic_knowledge(store, clinic_id)
    if not data.get("found"):
        return "Approved clinic facts: unavailable. Escalate if asked for clinic details."

    lines = [
        f"Clinic: {data['name']}",
        f"Timezone: {data['timezone']}",
    ]
    if data.get("website_url"):
        lines.append(f"Website: {data['website_url']}")

    hours = data.get("opening_hours") or []
    if hours:
        lines.append("Opening hours (clinic local):")
        for row in hours[:14]:
            lines.append(f"- {row['day']} {row['open']}–{row['close']}")
    else:
        lines.append("Opening hours: not configured yet — do not invent hours.")

    services = data.get("services") or []
    if services:
        lines.append("Bookable services:")
        for row in services[:20]:
            price = (row.get("price") or {}).get("display") or "price on request"
            lines.append(
                f"- {row['name']} ({row['duration_minutes']} min, {price}) id={row['id']}"
            )
    else:
        lines.append("Services: none approved yet — do not invent services.")

    lines.append(
        "If unsure or the answer is not above, say you do not have that on file and escalate."
    )
    return "\n".join(lines)
