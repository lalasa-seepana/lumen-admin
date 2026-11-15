from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.services.clinic_store import reset_clinic_store
from app.services.voice_pipeline import run_voice_turn
from app.services.voice_tools import execute_tool, refuses_medical_advice
from app.services.gnani_speech import MockSttClient, MockTtsClient
from app.services.llm_evon import LlmTurn, MockLlmClient


@pytest.fixture()
def store():
    return reset_clinic_store()


def _seed_clinic(store):
    clinic, membership = store.create_clinic_for_owner(
        user_id=uuid4(), name="Voice Clinic", timezone_name="Asia/Kolkata"
    )
    service = store.create_service(
        clinic_id=clinic.id,
        name="Aroma Swedish Massage",
        category="Heal Your Mind",
        duration_minutes=60,
        price_paise=320000,
    )
    # Monday 09:00–17:00
    store.add_availability_window(
        clinic_id=clinic.id, weekday=0, start_minute=9 * 60, end_minute=17 * 60
    )
    customer, _ = store.upsert_customer_by_email(
        clinic_id=clinic.id,
        email_normalized="demo-asha@example.com",
        full_name="DEMO-Asha Rao",
        phone_e164="+919876543210",
    )
    return clinic, membership, service, customer


def test_refuses_medical_advice_patterns():
    assert refuses_medical_advice("Can you diagnose my headache?")
    assert refuses_medical_advice("What medicine should I take?")
    assert not refuses_medical_advice("What massage services do you offer?")


def test_unknown_tool_rejected(store):
    clinic, *_ = _seed_clinic(store)
    ok, result, reason = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=None,
        tool_name="delete_customer",
        arguments={},
    )
    assert ok is False
    assert reason == "tool_not_allowed"
    assert store.list_tool_audits(clinic.id)[0].accepted is False


def test_clinic_spoof_rejected(store):
    clinic, *_ = _seed_clinic(store)
    ok, result, reason = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=None,
        tool_name="list_services",
        arguments={"clinic_id": str(uuid4())},
    )
    assert ok is False
    assert reason == "clinic_spoof_rejected"


def test_cross_clinic_denied(store):
    clinic_a, *_ = _seed_clinic(store)
    clinic_b, _m, _s, _c = _seed_clinic(store)
    ok, result, reason = execute_tool(
        store,
        clinic_id=clinic_a.id,
        voice_session_id=None,
        tool_name="list_services",
        arguments={},
        foreign_clinic_id=clinic_b.id,
    )
    assert ok is False
    assert reason == "cross_clinic_denied"


def test_list_services_and_booking_conflict(store):
    clinic, _m, service, customer = _seed_clinic(store)
    ok, listed, _ = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=None,
        tool_name="list_services",
        arguments={},
    )
    assert ok is True
    assert listed["services"][0]["name"] == "Aroma Swedish Massage"

    # Monday 10:00 Asia/Kolkata → 04:30 UTC
    start = datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc)
    ok, created, _ = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=None,
        tool_name="create_appointment",
        arguments={
            "service_id": str(service.id),
            "customer_id": str(customer.id),
            "starts_at_utc": start.isoformat(),
        },
    )
    assert ok is True

    ok2, result2, reason2 = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=None,
        tool_name="create_appointment",
        arguments={
            "service_id": str(service.id),
            "customer_id": str(customer.id),
            "starts_at_utc": (start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert ok2 is False
    assert reason2 == "appointment_conflict"


@pytest.mark.asyncio
async def test_pipeline_medical_refusal_escalates(store):
    clinic, *_rest = _seed_clinic(store)
    session = store.create_voice_session(
        clinic_id=clinic.id, language="en-IN", recording_consent=False
    )
    stt = MockSttClient(text="Please diagnose my back pain")
    tts = MockTtsClient()
    llm = MockLlmClient()
    result = await run_voice_turn(
        store,
        clinic_id=clinic.id,
        voice_session_id=session.id,
        language="en-IN",
        pcm=b"\x00\x00",
        stt=stt,
        tts=tts,
        llm=llm,
        recording_consent=False,
    )
    assert result.refused_medical is True
    assert result.escalated is True
    assert len(store.list_handovers(clinic.id)) == 1
    assert llm.calls == []  # medical path skips LLM


@pytest.mark.asyncio
async def test_pipeline_llm_unreachable_escalates(store):
    clinic, *_ = _seed_clinic(store)
    session = store.create_voice_session(
        clinic_id=clinic.id, language="en-IN", recording_consent=False
    )

    class BoomLlm:
        async def complete(self, *, messages, language):
            raise RuntimeError("llm_unreachable")

    result = await run_voice_turn(
        store,
        clinic_id=clinic.id,
        voice_session_id=session.id,
        language="en-IN",
        pcm=b"\x00\x00",
        stt=MockSttClient(text="Book a massage tomorrow"),
        tts=MockTtsClient(),
        llm=BoomLlm(),
    )
    assert result.llm_failed is True
    assert result.escalated is True
    assert store.list_handovers(clinic.id)[0].reason == "llm_unreachable"


@pytest.mark.asyncio
async def test_pipeline_tool_call_list_services(store):
    clinic, *_ = _seed_clinic(store)
    session = store.create_voice_session(
        clinic_id=clinic.id, language="en-IN", recording_consent=True
    )
    llm = MockLlmClient(
        script=[
            LlmTurn(
                assistant_text="I'm Rhea, an AI receptionist. Here are the services.",
                tool_calls=[
                    {
                        "id": "1",
                        "type": "function",
                        "function": {"name": "list_services", "arguments": "{}"},
                    }
                ],
                raw={},
            )
        ]
    )
    result = await run_voice_turn(
        store,
        clinic_id=clinic.id,
        voice_session_id=session.id,
        language="en-IN",
        pcm=b"\x00\x00",
        stt=MockSttClient(text="What services do you offer?"),
        tts=MockTtsClient(),
        llm=llm,
        recording_consent=True,
    )
    assert result.tool_results[0]["accepted"] is True
    assert "AI" in result.assistant_text or "ai" in result.assistant_text.lower()
    assert result.audio is not None
