from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from app.core.config import Settings
from app.services.calcom_sync import pick_event_type_id, sync_appointment_to_calcom
from app.services.integration_crypto import encrypt_secret
from app.tests.conftest import INTEGRATION_PEPPER, make_token
from app.tests.test_integration_ingest import auth_headers


def _settings() -> Settings:
    return Settings(
        SUPABASE_JWT_SECRET="test-jwt-secret-for-lala-epic1-isolation",
        SUPABASE_URL="https://example.supabase.co",
        LALA_INTEGRATION_KEY_PEPPER=INTEGRATION_PEPPER,
        LALA_DEFAULT_TIMEZONE="Asia/Kolkata",
    )


def test_pick_event_type_prefers_matching_duration():
    rows = [
        {"id": 1, "lengthInMinutes": 30, "title": "Short"},
        {"id": 2, "lengthInMinutes": 60, "title": "Hour"},
    ]
    assert pick_event_type_id(rows, duration_minutes=60, default_event_type_id=1) == 2
    assert pick_event_type_id(rows, duration_minutes=45, default_event_type_id=1) == 1


def test_create_appointment_syncs_to_calcom_and_keeps_lala_calendar(client, owner_a_id, store):
    token = make_token(owner_a_id)
    created = client.post(
        "/v1/clinics", headers=auth_headers(token), json={"name": "Cal Sync Clinic"}
    )
    assert created.status_code == 201
    clinic_id = UUID(created.json()["clinic"]["id"])

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
        email_normalized="patient@example.com",
        full_name="Patient Example",
        phone_e164="+919876543210",
    )
    store.update_clinic(clinic_id, scheduling_mode="calcom")
    store.upsert_calendar_provider_connection(
        clinic_id=clinic_id,
        provider="calcom",
        api_key_enc=encrypt_secret(INTEGRATION_PEPPER, "cal_live_test_key"),
        status="connected",
        config={
            "username": "demo",
            "default_event_type_id": 99,
            "event_types": [{"id": 99, "title": "Hour", "lengthInMinutes": 60}],
        },
    )

    start = datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc)
    with patch("app.services.appointments.get_settings", return_value=_settings()), patch(
        "app.services.calcom_sync.create_calcom_booking",
        return_value=(True, "cal_uid_abc", None),
    ) as mock_create:
        response = client.post(
            "/v1/appointments",
            headers=auth_headers(token),
            json={
                "customer_id": str(customer.id),
                "service_id": str(service.id),
                "starts_at_utc": start.isoformat(),
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["provider"] == "calcom"
    assert body["sync_status"] == "synced"
    assert body["external_event_id"] == "cal_uid_abc"
    assert body["customer_name"] == "Patient Example"

    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["attendee_email"] == "patient@example.com"
    assert kwargs["attendee_name"] == "Patient Example"
    assert kwargs["event_type_id"] == 99

    listed = client.get("/v1/appointments", headers=auth_headers(token))
    assert listed.status_code == 200
    assert any(row["id"] == body["id"] and row["external_event_id"] == "cal_uid_abc" for row in listed.json())


def test_voice_booking_syncs_to_calcom_with_customer_email(store):
    from app.services.voice_tools import execute_tool

    clinic, _ = store.create_clinic_for_owner(
        user_id=UUID("00000000-0000-0000-0000-0000000000aa"),
        name="Voice Cal Clinic",
        timezone_name="Asia/Kolkata",
    )
    service = store.create_service(
        clinic_id=clinic.id,
        name="Deep Tissue",
        category="Heal",
        duration_minutes=60,
        price_paise=380000,
    )
    store.add_availability_window(
        clinic_id=clinic.id, weekday=0, start_minute=9 * 60, end_minute=17 * 60
    )
    customer, _ = store.upsert_customer_by_email(
        clinic_id=clinic.id,
        email_normalized="voice-patient@example.com",
        full_name="Voice Patient",
        phone_e164=None,
    )
    store.update_clinic(clinic.id, scheduling_mode="calcom")
    store.upsert_calendar_provider_connection(
        clinic_id=clinic.id,
        provider="calcom",
        api_key_enc=encrypt_secret(INTEGRATION_PEPPER, "cal_live_voice"),
        status="connected",
        config={
            "default_event_type_id": 7,
            "event_types": [{"id": 7, "title": "Hour", "lengthInMinutes": 60}],
        },
    )
    session = store.create_voice_session(
        clinic_id=clinic.id, language="en-IN", recording_consent=False, actor_type="visitor"
    )
    store.update_voice_session(
        session.id,
        customer_id=customer.id,
        customer_verified_at=datetime.now(timezone.utc),
    )
    start = datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc)

    with patch("app.core.config.get_settings", return_value=_settings()), patch(
        "app.services.calcom_sync.create_calcom_booking",
        return_value=(True, "voice_cal_uid", None),
    ):
        ok, result, reason = execute_tool(
            store,
            clinic_id=clinic.id,
            voice_session_id=session.id,
            tool_name="create_appointment",
            arguments={
                "service_id": str(service.id),
                "starts_at_utc": start.isoformat(),
                "confirmed_by_visitor": True,
            },
        )

    assert ok is True, reason
    assert result["sync_status"] == "synced"
    assert result["external_event_id"] == "voice_cal_uid"
    assert result["calcom_email"] is True
    appt = store.get_appointment(clinic.id, UUID(result["appointment_id"]))
    assert appt is not None
    assert appt.provider == "calcom"
    assert appt.external_event_id == "voice_cal_uid"


def test_sync_skipped_without_customer_email(store):
    clinic, _ = store.create_clinic_for_owner(
        user_id=UUID("00000000-0000-0000-0000-0000000000bb"),
        name="No Email Clinic",
        timezone_name="Asia/Kolkata",
    )
    service = store.create_service(
        clinic_id=clinic.id,
        name="Consult",
        category="Care",
        duration_minutes=30,
        price_paise=None,
    )
    # Force a customer without a usable email by mutating after upsert.
    customer, _ = store.upsert_customer_by_email(
        clinic_id=clinic.id,
        email_normalized="placeholder@example.com",
        full_name="No Mail",
        phone_e164=None,
    )
    mutated = store.customers[customer.id]
    store.customers[customer.id] = type(mutated)(
        id=mutated.id,
        clinic_id=mutated.clinic_id,
        email_normalized="",
        full_name=mutated.full_name,
        phone_e164=mutated.phone_e164,
        possible_phone_duplicate=mutated.possible_phone_duplicate,
        created_at=mutated.created_at,
    )
    store.update_clinic(clinic.id, scheduling_mode="calcom")
    store.upsert_calendar_provider_connection(
        clinic_id=clinic.id,
        provider="calcom",
        api_key_enc=encrypt_secret(INTEGRATION_PEPPER, "cal_live_x"),
        status="connected",
        config={"default_event_type_id": 1, "event_types": [{"id": 1, "lengthInMinutes": 30}]},
    )
    appt = store.create_appointment(
        clinic_id=clinic.id,
        customer_id=customer.id,
        service_id=service.id,
        starts_at_utc=datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc),
        ends_at_utc=datetime(2026, 11, 16, 5, 0, tzinfo=timezone.utc),
        provider="calcom",
        sync_status="pending_provider",
    )
    with patch("app.services.calcom_sync.create_calcom_booking") as mock_create:
        out = sync_appointment_to_calcom(
            store, _settings(), clinic_id=clinic.id, appointment_id=appt.id
        )
    assert out["synced"] is False
    assert out["reason"] == "customer_email_required"
    mock_create.assert_not_called()
    refreshed = store.get_appointment(clinic.id, appt.id)
    assert refreshed is not None
    assert refreshed.sync_status == "needs_email"
