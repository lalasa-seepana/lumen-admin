from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.services.voice_tools import execute_tool
from app.tests.conftest import make_token
from app.tests.test_integration_ingest import auth_headers


def _create_clinic(client, token, name="Calendar Link Clinic"):
    response = client.post("/v1/clinics", headers=auth_headers(token), json={"name": name})
    assert response.status_code == 201
    return response.json()["clinic"]["id"]


def test_voice_booking_appears_on_calendar_and_conversation(client, owner_a_id, store):
    token = make_token(owner_a_id)
    clinic_id = UUID(_create_clinic(client, token))

    service = store.create_service(
        clinic_id=clinic_id,
        name="Swedish Massage",
        category="Relax",
        duration_minutes=60,
        price_paise=300000,
    )
    store.add_availability_window(
        clinic_id=clinic_id, weekday=0, start_minute=9 * 60, end_minute=17 * 60
    )
    customer, _ = store.upsert_customer_by_email(
        clinic_id=clinic_id,
        email_normalized="visitor@example.com",
        full_name="Visitor One",
        phone_e164="+919876543210",
    )

    created = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token),
        json={"language": "en-IN", "recording_consent": False},
    )
    assert created.status_code == 201
    session_id = UUID(created.json()["id"])
    store.update_voice_session(
        session_id,
        customer_id=customer.id,
        customer_verified_at=datetime.now(timezone.utc),
        actor_type="visitor",
    )

    start = datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc)
    ok, result, reason = execute_tool(
        store,
        clinic_id=clinic_id,
        voice_session_id=session_id,
        tool_name="create_appointment",
        arguments={
            "service_id": str(service.id),
            "starts_at_utc": start.isoformat(),
            "confirmed_by_visitor": True,
        },
    )
    assert ok is True, reason
    assert result is not None
    assert result["status"] == "booked"
    appointment_id = result["appointment_id"]

    appt = store.get_appointment(clinic_id, UUID(appointment_id))
    assert appt is not None
    assert appt.voice_session_id == session_id

    calendar = client.get("/v1/appointments", headers=auth_headers(token))
    assert calendar.status_code == 200
    rows = calendar.json()
    assert any(row["id"] == appointment_id for row in rows)
    booked = next(row for row in rows if row["id"] == appointment_id)
    assert booked["voice_session_id"] == str(session_id)
    assert booked["service_name"] == "Swedish Massage"

    conversation = store.get_conversation_by_session(session_id)
    assert conversation is not None

    listed = client.get("/v1/conversations", headers=auth_headers(token))
    assert listed.status_code == 200
    conv_row = next(row for row in listed.json() if row["id"] == str(conversation.id))
    assert conv_row["appointment_count"] == 1

    detail = client.get(
        f"/v1/conversations/{conversation.id}", headers=auth_headers(token)
    )
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["appointments"]) == 1
    assert body["appointments"][0]["id"] == appointment_id
    assert body["appointments"][0]["starts_at_utc"].startswith("2026-11-16")
