from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.core.phone import normalize_phone_e164
from app.services.booking_rules import within_availability as _within_availability
from app.services.clinic_store import ClinicStore

ALLOWED_TOOLS = {
    "get_clinic_knowledge",
    "list_services",
    "check_availability",
    "offer_alternative_slots",
    "remember_slot",
    "capture_visitor_details",
    "request_visitor_verification",
    "confirm_visitor_verification",
    "create_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "escalate",
}

DIAGNOSIS_PATTERNS = (
    "diagnos",
    "prescribe",
    "treatment plan",
    "what medicine",
    "should i take",
    "cure my",
    "medical advice",
)

CONSENT_TEXT_VERSION = "lala-voice-recording-v1"
CONSENT_TEXT = (
    "I agree to save this conversation's audio recording and transcript."
)
VERIFICATION_TTL_MINUTES = 10
VERIFICATION_MAX_ATTEMPTS = 5


SYSTEM_PROMPT = """You are Rhea, an AI receptionist. Always disclose you are an AI, not a clinician.
Scope: services, hours, availability, booking, handoff. No diagnosis, prescriptions, or treatment advice.
Grounding: use only approved clinic facts from the prompt card and tools. Never invent prices, hours, policies, or appointments.
If a fact is missing, say you do not have that on file and call escalate.
Respond in the caller's language (en/hi/te). Keep spoken replies short (1–3 sentences) for low latency.

Tools:
- get_clinic_knowledge / list_services for facts
- check_availability → remember_slot → explicit confirmation → create_appointment
- Never say a booking is confirmed unless create_appointment returned appointment_id with status booked
- Returning visitors: verify before history or changes
"""


def refuses_medical_advice(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in DIAGNOSIS_PATTERNS)


def tool_specs() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_clinic_knowledge",
                "description": (
                    "Fetch approved clinic facts: name, timezone, website, opening hours, "
                    "and bookable services. Call when the visitor asks about the clinic, "
                    "hours, prices, or policies. Do not invent missing fields."
                ),
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_services",
                "description": "List active clinic services the caller can book.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_availability",
                "description": "Check whether a proposed UTC start time fits clinic hours and has no conflict.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_id": {"type": "string"},
                        "starts_at_utc": {"type": "string", "description": "ISO-8601 UTC"},
                    },
                    "required": ["service_id", "starts_at_utc"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "offer_alternative_slots",
                "description": "Suggest nearby available slots when the requested time is unavailable.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_id": {"type": "string"},
                        "around_starts_at_utc": {"type": "string"},
                    },
                    "required": ["service_id", "around_starts_at_utc"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "remember_slot",
                "description": "Remember the visitor's selected service and start time pending confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_id": {"type": "string"},
                        "starts_at_utc": {"type": "string"},
                    },
                    "required": ["service_id", "starts_at_utc"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "capture_visitor_details",
                "description": "Collect name/email/phone for a new visitor. Does not prove identity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "full_name": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": "string"},
                    },
                    "required": ["full_name", "email"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "request_visitor_verification",
                "description": "Start OTP verification for a returning customer before private history or changes.",
                "parameters": {
                    "type": "object",
                    "properties": {"email": {"type": "string"}},
                    "required": ["email"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_visitor_verification",
                "description": "Confirm the OTP code for visitor verification.",
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_appointment",
                "description": (
                    "Create an appointment after explicit visitor confirmation. "
                    "Uses verified session customer when present."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_id": {"type": "string"},
                        "customer_id": {"type": "string"},
                        "starts_at_utc": {"type": "string"},
                        "confirmed_by_visitor": {"type": "boolean"},
                        "idempotency_key": {"type": "string"},
                    },
                    "required": ["service_id", "starts_at_utc", "confirmed_by_visitor"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reschedule_appointment",
                "description": "Reschedule an appointment owned by the verified visitor.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string"},
                        "starts_at_utc": {"type": "string"},
                        "confirmed_by_visitor": {"type": "boolean"},
                    },
                    "required": ["appointment_id", "starts_at_utc", "confirmed_by_visitor"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cancel_appointment",
                "description": "Cancel an appointment owned by the verified visitor.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string"},
                        "confirmed_by_visitor": {"type": "boolean"},
                    },
                    "required": ["appointment_id", "confirmed_by_visitor"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "escalate",
                "description": "Escalate to clinic staff when unsure or out of scope.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                    "required": ["reason", "summary"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def _parse_uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid_{field}") from exc


def _parse_dt(value: Any) -> datetime:
    text = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hash_code(code: str, session_id: UUID) -> str:
    material = f"{session_id}:{code.strip()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _session_or_none(store: ClinicStore, voice_session_id: Optional[UUID]):
    if voice_session_id is None:
        return None
    return store.get_voice_session(voice_session_id)


def _require_verified_visitor(session) -> UUID:
    if session is None:
        raise ValueError("visitor_session_required")
    if session.actor_type == "owner":
        if session.customer_id is None:
            raise ValueError("customer_required")
        return session.customer_id
    if session.customer_id is None or session.customer_verified_at is None:
        raise ValueError("visitor_not_verified")
    return session.customer_id


def _slot_free(
    store: ClinicStore,
    clinic_id: UUID,
    starts: datetime,
    ends: datetime,
    *,
    ignore_appointment_id: Optional[UUID] = None,
) -> bool:
    for existing in store.appointments.values():
        if existing.clinic_id != clinic_id or existing.status == "cancelled":
            continue
        if ignore_appointment_id and existing.id == ignore_appointment_id:
            continue
        if starts < existing.ends_at_utc and ends > existing.starts_at_utc:
            return False
    return True


def _offer_slots(
    store: ClinicStore,
    clinic_id: UUID,
    service,
    around: datetime,
    clinic_timezone: str,
    *,
    limit: int = 3,
) -> List[Dict[str, str]]:
    offers: List[Dict[str, str]] = []
    for day_offset in range(0, 7):
        for hour in range(9, 17):
            for minute in (0, 30):
                candidate = (around + timedelta(days=day_offset)).replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if candidate <= around:
                    continue
                ends = candidate + timedelta(minutes=service.duration_minutes)
                if not _within_availability(store, clinic_id, candidate, ends, clinic_timezone):
                    continue
                if not _slot_free(store, clinic_id, candidate, ends):
                    continue
                offers.append(
                    {
                        "starts_at_utc": candidate.isoformat(),
                        "ends_at_utc": ends.isoformat(),
                        "clinic_timezone": clinic_timezone,
                    }
                )
                if len(offers) >= limit:
                    return offers
    return offers


def execute_tool(
    store: ClinicStore,
    *,
    clinic_id: UUID,
    voice_session_id: Optional[UUID],
    tool_name: str,
    arguments: Dict[str, Any],
    foreign_clinic_id: Optional[UUID] = None,
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Validate and execute one tool. Returns (accepted, result, reason)."""
    args = dict(arguments or {})
    clinic = store.get_clinic(clinic_id)
    clinic_timezone = clinic.timezone if clinic else "Asia/Kolkata"
    session = _session_or_none(store, voice_session_id)

    for key in ("clinic_id", "tenant_id", "clinicId"):
        if key in args:
            store.add_tool_audit(
                clinic_id=clinic_id,
                voice_session_id=voice_session_id,
                tool_name=tool_name,
                accepted=False,
                reason="clinic_spoof_rejected",
                arguments=args,
            )
            return False, {"error": "clinic_spoof_rejected"}, "clinic_spoof_rejected"

    if foreign_clinic_id is not None and foreign_clinic_id != clinic_id:
        store.add_tool_audit(
            clinic_id=clinic_id,
            voice_session_id=voice_session_id,
            tool_name=tool_name,
            accepted=False,
            reason="cross_clinic_denied",
            arguments=args,
        )
        return False, {"error": "cross_clinic_denied"}, "cross_clinic_denied"

    if tool_name not in ALLOWED_TOOLS:
        store.add_tool_audit(
            clinic_id=clinic_id,
            voice_session_id=voice_session_id,
            tool_name=tool_name,
            accepted=False,
            reason="tool_not_allowed",
            arguments=args,
        )
        return False, {"error": "tool_not_allowed"}, "tool_not_allowed"

    try:
        if tool_name == "get_clinic_knowledge":
            from app.services.clinic_knowledge import build_clinic_knowledge

            result = build_clinic_knowledge(store, clinic_id)
        elif tool_name == "list_services":
            rows = store.list_services(clinic_id)
            result = {
                "services": [
                    {
                        "id": str(row.id),
                        "name": row.name,
                        "category": row.category,
                        "duration_minutes": row.duration_minutes,
                    }
                    for row in rows
                ],
                "clinic_timezone": clinic_timezone,
            }
        elif tool_name == "check_availability":
            service_id = _parse_uuid(args.get("service_id"), "service_id")
            service = store.get_service(clinic_id, service_id)
            if service is None or not service.active:
                raise ValueError("service_not_found")
            starts = _parse_dt(args.get("starts_at_utc"))
            ends = starts + timedelta(minutes=service.duration_minutes)
            available = _within_availability(store, clinic_id, starts, ends, clinic_timezone)
            conflict = not _slot_free(store, clinic_id, starts, ends) if available else False
            result = {
                "available": available and not conflict,
                "starts_at_utc": starts.isoformat(),
                "ends_at_utc": ends.isoformat(),
                "clinic_timezone": clinic_timezone,
                "reason": None
                if available and not conflict
                else ("outside_hours" if not available else "conflict"),
            }
        elif tool_name == "offer_alternative_slots":
            service_id = _parse_uuid(args.get("service_id"), "service_id")
            service = store.get_service(clinic_id, service_id)
            if service is None or not service.active:
                raise ValueError("service_not_found")
            around = _parse_dt(args.get("around_starts_at_utc"))
            result = {
                "alternatives": _offer_slots(
                    store, clinic_id, service, around, clinic_timezone
                ),
                "clinic_timezone": clinic_timezone,
            }
        elif tool_name == "remember_slot":
            if session is None:
                raise ValueError("visitor_session_required")
            service_id = _parse_uuid(args.get("service_id"), "service_id")
            starts = _parse_dt(args.get("starts_at_utc"))
            service = store.get_service(clinic_id, service_id)
            if service is None or not service.active:
                raise ValueError("service_not_found")
            ends = starts + timedelta(minutes=service.duration_minutes)
            if not _within_availability(store, clinic_id, starts, ends, clinic_timezone):
                raise ValueError("outside_hours")
            if not _slot_free(store, clinic_id, starts, ends):
                raise ValueError("appointment_conflict")
            store.update_voice_session(
                session.id,
                selected_service_id=service_id,
                selected_starts_at_utc=starts,
            )
            result = {
                "remembered": True,
                "service_id": str(service_id),
                "service_name": service.name,
                "starts_at_utc": starts.isoformat(),
                "clinic_timezone": clinic_timezone,
                "readback": (
                    f"{service.name} on {starts.isoformat()} "
                    f"(clinic timezone {clinic_timezone}). Confirm to book."
                ),
            }
        elif tool_name == "capture_visitor_details":
            if session is None:
                raise ValueError("visitor_session_required")
            full_name = str(args.get("full_name") or "").strip()
            email = str(args.get("email") or "").strip().lower()
            phone_raw = str(args.get("phone") or "").strip() or None
            if not full_name or "@" not in email:
                raise ValueError("invalid_visitor_details")
            phone = normalize_phone_e164(phone_raw) if phone_raw else None
            existing = store.customers_by_clinic_email.get((clinic_id, email))
            if existing:
                # Ambiguous/returning — do not auto-bind; require verification.
                store.update_voice_session(
                    session.id,
                    pending_full_name=full_name,
                    pending_email=email,
                    pending_phone=phone,
                    callback_contact=phone or email,
                )
                result = {
                    "status": "verification_required",
                    "message": "An existing record may match. Verify before continuing.",
                    # Do not reveal whether a record exists beyond needing verification.
                }
            else:
                customer, outcome = store.upsert_customer_by_email(
                    clinic_id=clinic_id,
                    email_normalized=email,
                    full_name=full_name,
                    phone_e164=phone,
                )
                store.update_voice_session(
                    session.id,
                    customer_id=customer.id,
                    customer_verified_at=datetime.now(timezone.utc),
                    pending_full_name=full_name,
                    pending_email=email,
                    pending_phone=phone,
                    callback_contact=phone or email,
                )
                result = {
                    "status": "captured",
                    "customer_id": str(customer.id),
                    "outcome": outcome,
                    "verified": True,
                }
        elif tool_name == "request_visitor_verification":
            if session is None:
                raise ValueError("visitor_session_required")
            email = str(args.get("email") or "").strip().lower()
            if "@" not in email:
                raise ValueError("invalid_email")
            # Always respond generically — do not reveal whether the email exists.
            code = f"{secrets.randbelow(1_000_000):06d}"
            store.update_voice_session(
                session.id,
                pending_email=email,
                verification_code_hash=_hash_code(code, session.id),
                verification_expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=VERIFICATION_TTL_MINUTES),
                verification_attempts=0,
                customer_verified_at=None,
            )
            # Dev/mock delivery: attach code only when customer exists in this clinic.
            customer_id = store.customers_by_clinic_email.get((clinic_id, email))
            result = {
                "status": "code_sent_if_match",
                "expires_in_minutes": VERIFICATION_TTL_MINUTES,
                "delivery": "dev_inline" if customer_id else "suppressed",
            }
            if customer_id:
                result["dev_code"] = code
                result["customer_matched"] = True
            else:
                result["customer_matched"] = False
        elif tool_name == "confirm_visitor_verification":
            if session is None:
                raise ValueError("visitor_session_required")
            code = str(args.get("code") or "").strip()
            if not session.verification_code_hash or not session.verification_expires_at:
                raise ValueError("verification_not_started")
            if session.verification_attempts >= VERIFICATION_MAX_ATTEMPTS:
                raise ValueError("verification_rate_limited")
            store.update_voice_session(
                session.id, verification_attempts=session.verification_attempts + 1
            )
            if datetime.now(timezone.utc) > session.verification_expires_at:
                raise ValueError("verification_expired")
            if not hmac.compare_digest(
                session.verification_code_hash, _hash_code(code, session.id)
            ):
                raise ValueError("verification_failed")
            email = (session.pending_email or "").lower()
            customer_id = store.customers_by_clinic_email.get((clinic_id, email))
            if customer_id is None:
                raise ValueError("verification_failed")
            store.update_voice_session(
                session.id,
                customer_id=customer_id,
                customer_verified_at=datetime.now(timezone.utc),
                verification_code_hash=None,
                verification_expires_at=None,
            )
            result = {"verified": True, "customer_id": str(customer_id)}
        elif tool_name == "create_appointment":
            if not bool(args.get("confirmed_by_visitor")) and voice_session_id is not None:
                # Owner/test path without session may omit confirmation.
                if session is not None and session.actor_type == "visitor":
                    raise ValueError("confirmation_required")
            service_id = _parse_uuid(
                args.get("service_id")
                or (session.selected_service_id if session else None),
                "service_id",
            )
            starts = _parse_dt(
                args.get("starts_at_utc")
                or (session.selected_starts_at_utc.isoformat() if session and session.selected_starts_at_utc else None)
            )
            service = store.get_service(clinic_id, service_id)
            if service is None or not service.active:
                raise ValueError("service_not_found")

            if session is not None and session.actor_type == "visitor":
                customer_id = _require_verified_visitor(session)
            else:
                customer_id = _parse_uuid(args.get("customer_id"), "customer_id")
                customer = store.get_customer(clinic_id, customer_id)
                if customer is None:
                    raise ValueError("customer_not_found")

            ends = starts + timedelta(minutes=service.duration_minutes)
            # Re-check availability at submission time.
            if not _within_availability(store, clinic_id, starts, ends, clinic_timezone):
                raise ValueError("outside_hours")
            if not _slot_free(store, clinic_id, starts, ends):
                raise ValueError("appointment_conflict")

            idem = args.get("idempotency_key")
            if idem:
                existing = store.get_appointment_by_idempotency(
                    clinic_id=clinic_id, idempotency_key=str(idem)
                )
                if existing is not None:
                    result = {
                        "appointment_id": str(existing.id),
                        "status": existing.status,
                        "starts_at_utc": existing.starts_at_utc.isoformat(),
                        "ends_at_utc": existing.ends_at_utc.isoformat(),
                        "idempotent_replay": True,
                        "clinic_timezone": clinic_timezone,
                    }
                    store.add_tool_audit(
                        clinic_id=clinic_id,
                        voice_session_id=voice_session_id,
                        tool_name=tool_name,
                        accepted=True,
                        reason=None,
                        arguments=args,
                    )
                    return True, result, None

            # External provider uncertainty → pending (reconcile later).
            provider = "lala"
            sync_status = "local"
            status = "booked"
            if clinic and clinic.scheduling_mode == "google" and clinic.google_status == "connected":
                provider = "google"
                # Without a verified live provider call in this path, mark pending.
                if not clinic.google_refresh_token_enc or str(
                    clinic.google_refresh_token_enc
                ).startswith("stub:"):
                    status = "pending"
                    sync_status = "pending_provider"
            elif clinic and clinic.scheduling_mode == "calcom":
                provider = "calcom"
                sync_status = "pending_provider"

            appt = store.create_appointment(
                clinic_id=clinic_id,
                customer_id=customer_id,
                service_id=service_id,
                starts_at_utc=starts,
                ends_at_utc=ends,
                idempotency_key=str(idem) if idem else None,
                provider=provider,
                sync_status=sync_status,
                status=status,
                voice_session_id=voice_session_id,
            )
            from app.core.config import get_settings

            settings = get_settings()
            if voice_session_id is not None:
                # Ensure a conversation row exists so the booking is visible from Conversations
                # even when recording consent (and thus a transcript) was never given.
                from app.services import conversations as conversation_service

                conversation_service.ensure_conversation_for_session(
                    store, settings, voice_session_id=voice_session_id
                )
            if clinic and clinic.scheduling_mode == "calcom":
                from app.services.calcom_sync import sync_appointment_to_calcom

                sync_appointment_to_calcom(
                    store, settings, clinic_id=clinic_id, appointment_id=appt.id
                )
                refreshed = store.get_appointment(clinic_id, appt.id)
                if refreshed is not None:
                    appt = refreshed
                    status = appt.status
                    sync_status = appt.sync_status
                    provider = appt.provider
            store.add_activity_event(
                clinic_id=clinic_id,
                actor_type="system",
                action="appointment.created",
                entity_type="appointment",
                entity_id=appt.id,
                payload={
                    "source": "voice_tool",
                    "status": status,
                    "provider": provider,
                    "sync_status": sync_status,
                    "external_event_id": appt.external_event_id,
                    "voice_session_id": str(voice_session_id) if voice_session_id else None,
                },
            )
            result = {
                "appointment_id": str(appt.id),
                "status": appt.status,
                "starts_at_utc": appt.starts_at_utc.isoformat(),
                "ends_at_utc": appt.ends_at_utc.isoformat(),
                "service_name": service.name,
                "clinic_timezone": clinic_timezone,
                "provider": provider,
                "sync_status": sync_status,
                "external_event_id": appt.external_event_id,
                "calcom_email": sync_status == "synced",
            }
        elif tool_name == "reschedule_appointment":
            appointment_id = _parse_uuid(args.get("appointment_id"), "appointment_id")
            existing = store.get_appointment(clinic_id, appointment_id)
            if existing is None:
                raise ValueError("appointment_not_found")
            if session is not None and session.actor_type == "visitor":
                if not bool(args.get("confirmed_by_visitor")):
                    raise ValueError("confirmation_required")
                owner_id = _require_verified_visitor(session)
                if existing.customer_id != owner_id:
                    raise ValueError("appointment_not_owned")
            service = store.get_service(clinic_id, existing.service_id)
            if service is None:
                raise ValueError("service_not_found")
            starts = _parse_dt(args.get("starts_at_utc"))
            ends = starts + timedelta(minutes=service.duration_minutes)
            if not _within_availability(store, clinic_id, starts, ends, clinic_timezone):
                raise ValueError("outside_hours")
            if not _slot_free(
                store, clinic_id, starts, ends, ignore_appointment_id=appointment_id
            ):
                raise ValueError("appointment_conflict")
            appt = store.reschedule_appointment(
                clinic_id=clinic_id,
                appointment_id=appointment_id,
                starts_at_utc=starts,
                ends_at_utc=ends,
            )
            store.add_activity_event(
                clinic_id=clinic_id,
                actor_type="system",
                action="appointment.rescheduled",
                entity_type="appointment",
                entity_id=appt.id,
                payload={"source": "voice_tool"},
            )
            result = {
                "appointment_id": str(appt.id),
                "status": appt.status,
                "starts_at_utc": appt.starts_at_utc.isoformat(),
                "ends_at_utc": appt.ends_at_utc.isoformat(),
                "clinic_timezone": clinic_timezone,
            }
        elif tool_name == "cancel_appointment":
            appointment_id = _parse_uuid(args.get("appointment_id"), "appointment_id")
            existing = store.get_appointment(clinic_id, appointment_id)
            if existing is None:
                raise ValueError("appointment_not_found")
            if session is not None and session.actor_type == "visitor":
                if not bool(args.get("confirmed_by_visitor")):
                    raise ValueError("confirmation_required")
                owner_id = _require_verified_visitor(session)
                if existing.customer_id != owner_id:
                    raise ValueError("appointment_not_owned")
            appt = store.cancel_appointment(clinic_id=clinic_id, appointment_id=appointment_id)
            store.add_activity_event(
                clinic_id=clinic_id,
                actor_type="system",
                action="appointment.cancelled",
                entity_type="appointment",
                entity_id=appt.id,
                payload={"source": "voice_tool"},
            )
            result = {"appointment_id": str(appt.id), "status": appt.status}
        elif tool_name == "escalate":
            reason = str(args.get("reason") or "").strip() or "unspecified"
            summary = str(args.get("summary") or "").strip() or "Caller needs staff help"
            callback = None
            if session is not None:
                callback = session.callback_contact or session.pending_email or session.pending_phone
            handover = store.create_handover(
                clinic_id=clinic_id,
                voice_session_id=voice_session_id,
                reason=reason,
                summary=summary,
                callback_contact=callback,
            )
            store.add_activity_event(
                clinic_id=clinic_id,
                actor_type="system",
                action="handover.created",
                entity_type="handover",
                entity_id=handover.id,
                payload={"reason": reason, "callback_contact": callback},
            )
            result = {
                "handover_id": str(handover.id),
                "status": handover.status,
                "callback_contact": callback,
            }
        else:
            raise ValueError("tool_not_allowed")
    except ValueError as exc:
        reason = str(exc)
        store.add_tool_audit(
            clinic_id=clinic_id,
            voice_session_id=voice_session_id,
            tool_name=tool_name,
            accepted=False,
            reason=reason,
            arguments=args,
        )
        return False, {"error": reason}, reason

    store.add_tool_audit(
        clinic_id=clinic_id,
        voice_session_id=voice_session_id,
        tool_name=tool_name,
        accepted=True,
        reason=None,
        arguments=args,
    )
    return True, result, None
