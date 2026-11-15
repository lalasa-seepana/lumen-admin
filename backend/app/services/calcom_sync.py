from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx

from app.core.config import Settings
from app.services.clinic_store import ClinicStore
from app.services.integration_crypto import decrypt_secret

logger = logging.getLogger(__name__)

_CALCOM_API = "https://api.cal.com/v2"
_BOOKINGS_API_VERSION = "2026-02-25"
_EVENT_TYPES_API_VERSION = "2026-06-12"
_ME_API_VERSION = "2024-08-13"


def calcom_headers(api_key: str, *, api_version: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "cal-api-version": api_version,
        "Content-Type": "application/json",
    }


def _decrypt_api_key(settings: Settings, api_key_enc: Optional[str]) -> Optional[str]:
    if not api_key_enc:
        return None
    pepper = settings.lala_integration_key_pepper
    if not pepper.strip():
        return None
    try:
        return decrypt_secret(pepper, api_key_enc)
    except ValueError:
        return None


def _normalize_event_types(payload: Any) -> List[Dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    rows: List[Any]
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict) and isinstance(data.get("eventTypeGroups"), list):
        rows = []
        for group in data["eventTypeGroups"]:
            if isinstance(group, dict) and isinstance(group.get("eventTypes"), list):
                rows.extend(group["eventTypes"])
    elif isinstance(data, dict) and isinstance(data.get("eventTypes"), list):
        rows = data["eventTypes"]
    else:
        rows = []
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        length = row.get("lengthInMinutes")
        if length is None:
            length = row.get("length")
        out.append(
            {
                "id": int(row["id"]),
                "title": row.get("title") or row.get("slug") or f"Event {row['id']}",
                "slug": row.get("slug"),
                "lengthInMinutes": int(length) if length is not None else None,
            }
        )
    return out


def fetch_event_types(api_key: str, *, timeout: float = 15.0) -> List[Dict[str, Any]]:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            f"{_CALCOM_API}/event-types",
            headers=calcom_headers(api_key, api_version=_EVENT_TYPES_API_VERSION),
        )
    if response.status_code != 200:
        # Fall back to older header used by /me for accounts that reject the new version.
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                f"{_CALCOM_API}/event-types",
                headers=calcom_headers(api_key, api_version=_ME_API_VERSION),
            )
    if response.status_code != 200:
        logger.warning("calcom event-types failed: %s %s", response.status_code, response.text[:300])
        return []
    try:
        return _normalize_event_types(response.json())
    except Exception:
        logger.exception("calcom event-types parse failed")
        return []


async def fetch_event_types_async(api_key: str, *, timeout: float = 15.0) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"{_CALCOM_API}/event-types",
            headers=calcom_headers(api_key, api_version=_EVENT_TYPES_API_VERSION),
        )
        if response.status_code != 200:
            response = await client.get(
                f"{_CALCOM_API}/event-types",
                headers=calcom_headers(api_key, api_version=_ME_API_VERSION),
            )
    if response.status_code != 200:
        logger.warning("calcom event-types failed: %s %s", response.status_code, response.text[:300])
        return []
    try:
        return _normalize_event_types(response.json())
    except Exception:
        logger.exception("calcom event-types parse failed")
        return []


def pick_event_type_id(
    event_types: List[Dict[str, Any]],
    *,
    duration_minutes: int,
    default_event_type_id: Optional[int] = None,
) -> Optional[int]:
    matches = [
        row
        for row in event_types
        if row.get("lengthInMinutes") is not None and int(row["lengthInMinutes"]) == duration_minutes
    ]
    if matches:
        return int(matches[0]["id"])
    if default_event_type_id is not None:
        return int(default_event_type_id)
    if event_types:
        return int(event_types[0]["id"])
    return None


def _utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def create_calcom_booking(
    api_key: str,
    *,
    event_type_id: int,
    starts_at_utc: datetime,
    attendee_name: str,
    attendee_email: str,
    time_zone: str,
    length_in_minutes: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    phone_e164: Optional[str] = None,
    timeout: float = 20.0,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Create a Cal.com booking. Returns (ok, booking_uid_or_id, error_code).

    Cal.com emails the attendee when the booking is created with a real email.
    """
    body: Dict[str, Any] = {
        "start": _utc_z(starts_at_utc),
        "eventTypeId": event_type_id,
        "attendee": {
            "name": attendee_name or attendee_email.split("@")[0],
            "email": attendee_email,
            "timeZone": time_zone or "UTC",
            "language": "en",
        },
    }
    if length_in_minutes:
        body["lengthInMinutes"] = length_in_minutes
    if phone_e164:
        body["attendee"]["phoneNumber"] = phone_e164
    if metadata:
        body["metadata"] = metadata

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{_CALCOM_API}/bookings",
                headers=calcom_headers(api_key, api_version=_BOOKINGS_API_VERSION),
                json=body,
            )
    except httpx.TimeoutException:
        return False, None, "calcom_timeout"
    except httpx.HTTPError:
        return False, None, "calcom_http_error"

    if response.status_code not in {200, 201}:
        logger.warning("calcom booking failed: %s %s", response.status_code, response.text[:500])
        return False, None, f"calcom_http_{response.status_code}"

    try:
        payload = response.json()
    except Exception:
        return False, None, "calcom_bad_response"

    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        data = payload if isinstance(payload, dict) else {}
    uid = data.get("uid") or data.get("id")
    if uid is None:
        return False, None, "calcom_missing_uid"
    return True, str(uid), None


def sync_appointment_to_calcom(
    store: ClinicStore,
    settings: Settings,
    *,
    clinic_id: UUID,
    appointment_id: UUID,
) -> Dict[str, Any]:
    """Push a Clinic Dial appointment to Cal.com when scheduling_mode is calcom and a key is connected.

    Always keeps the Clinic Dial calendar row. On success, marks provider=calcom and stores external_event_id.
    Cal.com sends the customer confirmation email for the attendee email.
    """
    clinic = store.get_clinic(clinic_id)
    if clinic is None:
        return {"synced": False, "reason": "clinic_not_found"}
    if clinic.scheduling_mode != "calcom":
        return {"synced": False, "reason": "scheduling_mode_not_calcom"}

    connection = store.get_calendar_provider_connection(clinic_id, "calcom")
    if connection is None or connection.status != "connected" or not connection.api_key_enc:
        return {"synced": False, "reason": "calcom_not_connected"}

    appointment = store.get_appointment(clinic_id, appointment_id)
    if appointment is None:
        return {"synced": False, "reason": "appointment_not_found"}
    if appointment.external_event_id and appointment.sync_status == "synced":
        return {"synced": True, "reason": "already_synced", "external_event_id": appointment.external_event_id}

    customer = store.get_customer(clinic_id, appointment.customer_id)
    if customer is None:
        return {"synced": False, "reason": "customer_not_found"}
    email = (customer.email_normalized or "").strip().lower()
    if not email or "@" not in email:
        store.update_appointment_sync(
            clinic_id=clinic_id,
            appointment_id=appointment_id,
            provider="calcom",
            sync_status="needs_email",
            external_event_id=appointment.external_event_id,
        )
        return {"synced": False, "reason": "customer_email_required"}

    api_key = _decrypt_api_key(settings, connection.api_key_enc)
    if not api_key:
        store.update_appointment_sync(
            clinic_id=clinic_id,
            appointment_id=appointment_id,
            provider="calcom",
            sync_status="sync_error",
            external_event_id=appointment.external_event_id,
        )
        return {"synced": False, "reason": "calcom_key_decrypt_failed"}

    config = dict(connection.config or {})
    event_types = config.get("event_types") or []
    if not isinstance(event_types, list) or not event_types:
        event_types = fetch_event_types(api_key)
        if event_types:
            config["event_types"] = event_types
            if not config.get("default_event_type_id") and event_types:
                config["default_event_type_id"] = event_types[0]["id"]
            store.upsert_calendar_provider_connection(
                clinic_id=clinic_id,
                provider="calcom",
                status="connected",
                config=config,
                last_error=None,
            )

    service = store.get_service(clinic_id, appointment.service_id)
    duration = service.duration_minutes if service else None
    default_id = config.get("default_event_type_id")
    try:
        default_id_int = int(default_id) if default_id is not None else None
    except (TypeError, ValueError):
        default_id_int = None
    event_type_id = pick_event_type_id(
        event_types if isinstance(event_types, list) else [],
        duration_minutes=int(duration or 30),
        default_event_type_id=default_id_int,
    )
    if event_type_id is None:
        store.update_appointment_sync(
            clinic_id=clinic_id,
            appointment_id=appointment_id,
            provider="calcom",
            sync_status="sync_error",
            external_event_id=None,
        )
        store.upsert_calendar_provider_connection(
            clinic_id=clinic_id,
            provider="calcom",
            status="connected",
            last_error="No Cal.com event types available to book against",
            config=config,
        )
        return {"synced": False, "reason": "calcom_no_event_type"}

    ok, external_id, err = create_calcom_booking(
        api_key,
        event_type_id=event_type_id,
        starts_at_utc=appointment.starts_at_utc,
        attendee_name=customer.full_name,
        attendee_email=email,
        time_zone=clinic.timezone,
        length_in_minutes=duration,
        phone_e164=customer.phone_e164,
        metadata={
            "lala_appointment_id": str(appointment.id),
            "lala_clinic_id": str(clinic_id),
            "lala_service_name": service.name if service else None,
        },
    )
    if not ok:
        store.update_appointment_sync(
            clinic_id=clinic_id,
            appointment_id=appointment_id,
            provider="calcom",
            sync_status="pending_provider",
            external_event_id=None,
        )
        store.upsert_calendar_provider_connection(
            clinic_id=clinic_id,
            provider="calcom",
            status="connected",
            last_error=err or "calcom_booking_failed",
            config=config,
            last_sync_at=None,
        )
        return {"synced": False, "reason": err or "calcom_booking_failed"}

    store.update_appointment_sync(
        clinic_id=clinic_id,
        appointment_id=appointment_id,
        provider="calcom",
        sync_status="synced",
        external_event_id=external_id,
    )
    store.upsert_calendar_provider_connection(
        clinic_id=clinic_id,
        provider="calcom",
        status="connected",
        last_sync_at=datetime.now(timezone.utc),
        last_error=None,
        config=config,
    )
    return {
        "synced": True,
        "external_event_id": external_id,
        "event_type_id": event_type_id,
        "attendee_email": email,
        "email_via": "calcom",
    }
