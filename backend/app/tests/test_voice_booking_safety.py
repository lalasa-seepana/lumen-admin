from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.clinic_store import reset_clinic_store
from app.services.gnani_speech import MockSttClient, MockTtsClient
from app.services.llm_evon import LlmTurn, MockLlmClient
from app.services.voice_pipeline import run_voice_turn
from app.services.voice_tools import execute_tool


@pytest.fixture()
def store():
    return reset_clinic_store()


def _seed(store):
    clinic, _ = store.create_clinic_for_owner(
        user_id=uuid4(), name="Safety Clinic", timezone_name="Asia/Kolkata"
    )
    service = store.create_service(
        clinic_id=clinic.id,
        name="Deep Tissue Massage",
        category="Heal Your Mind",
        duration_minutes=60,
        price_paise=380000,
    )
    store.add_availability_window(
        clinic_id=clinic.id, weekday=0, start_minute=9 * 60, end_minute=17 * 60
    )
    customer, _ = store.upsert_customer_by_email(
        clinic_id=clinic.id,
        email_normalized="demo-asha@example.com",
        full_name="DEMO-Asha Rao",
        phone_e164="+919876543210",
    )
    return clinic, service, customer


@pytest.mark.asyncio
async def test_failed_create_never_announces_success(store):
    clinic, service, customer = _seed(store)
    session = store.create_voice_session(
        clinic_id=clinic.id, language="en-IN", recording_consent=False, actor_type="visitor"
    )
    store.update_voice_session(
        session.id,
        customer_id=customer.id,
        customer_verified_at=datetime.now(timezone.utc),
    )
    # Monday 10:00 Asia/Kolkata
    start = datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc)
    store.create_appointment(
        clinic_id=clinic.id,
        customer_id=customer.id,
        service_id=service.id,
        starts_at_utc=start,
        ends_at_utc=datetime(2026, 11, 16, 5, 30, tzinfo=timezone.utc),
    )
    llm = MockLlmClient(
        script=[
            LlmTurn(
                assistant_text="Your appointment is confirmed.",
                tool_calls=[
                    {
                        "id": "1",
                        "type": "function",
                        "function": {
                            "name": "create_appointment",
                            "arguments": (
                                f'{{"service_id":"{service.id}",'
                                f'"starts_at_utc":"{start.isoformat()}",'
                                f'"confirmed_by_visitor":true}}'
                            ),
                        },
                    }
                ],
                raw={},
            ),
            LlmTurn(
                assistant_text="Your appointment is confirmed.",
                tool_calls=[],
                raw={},
            ),
        ]
    )
    result = await run_voice_turn(
        store,
        clinic_id=clinic.id,
        voice_session_id=session.id,
        language="en-IN",
        pcm=b"\x00\x00",
        stt=MockSttClient(text="Book me for that slot"),
        tts=MockTtsClient(),
        llm=llm,
    )
    assert result.tool_results[0]["accepted"] is False
    assert result.booking_confirmed is False
    assert "confirmed" not in result.assistant_text.lower() or "could not confirm" in result.assistant_text.lower()


def test_unverified_visitor_cannot_reschedule(store):
    clinic, service, customer = _seed(store)
    session = store.create_voice_session(
        clinic_id=clinic.id, language="en-IN", recording_consent=False, actor_type="visitor"
    )
    start = datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc)
    appt = store.create_appointment(
        clinic_id=clinic.id,
        customer_id=customer.id,
        service_id=service.id,
        starts_at_utc=start,
        ends_at_utc=datetime(2026, 11, 16, 5, 30, tzinfo=timezone.utc),
    )
    ok, result, reason = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=session.id,
        tool_name="reschedule_appointment",
        arguments={
            "appointment_id": str(appt.id),
            "starts_at_utc": datetime(2026, 11, 16, 6, 30, tzinfo=timezone.utc).isoformat(),
            "confirmed_by_visitor": True,
        },
    )
    assert ok is False
    assert reason == "visitor_not_verified"


def test_verified_visitor_cannot_change_others_appointment(store):
    clinic, service, customer = _seed(store)
    other, _ = store.upsert_customer_by_email(
        clinic_id=clinic.id,
        email_normalized="demo-other@example.com",
        full_name="DEMO-Other",
        phone_e164=None,
    )
    session = store.create_voice_session(
        clinic_id=clinic.id, language="en-IN", recording_consent=False, actor_type="visitor"
    )
    store.update_voice_session(
        session.id,
        customer_id=other.id,
        customer_verified_at=datetime.now(timezone.utc),
    )
    appt = store.create_appointment(
        clinic_id=clinic.id,
        customer_id=customer.id,
        service_id=service.id,
        starts_at_utc=datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc),
        ends_at_utc=datetime(2026, 11, 16, 5, 30, tzinfo=timezone.utc),
    )
    ok, _result, reason = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=session.id,
        tool_name="reschedule_appointment",
        arguments={
            "appointment_id": str(appt.id),
            "starts_at_utc": datetime(2026, 11, 16, 6, 30, tzinfo=timezone.utc).isoformat(),
            "confirmed_by_visitor": True,
        },
    )
    assert ok is False
    assert reason == "appointment_not_owned"


def test_visitor_create_requires_confirmation(store):
    clinic, service, customer = _seed(store)
    session = store.create_voice_session(
        clinic_id=clinic.id, language="en-IN", recording_consent=False, actor_type="visitor"
    )
    store.update_voice_session(
        session.id,
        customer_id=customer.id,
        customer_verified_at=datetime.now(timezone.utc),
    )
    ok, _result, reason = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=session.id,
        tool_name="create_appointment",
        arguments={
            "service_id": str(service.id),
            "starts_at_utc": datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc).isoformat(),
            "confirmed_by_visitor": False,
        },
    )
    assert ok is False
    assert reason == "confirmation_required"
