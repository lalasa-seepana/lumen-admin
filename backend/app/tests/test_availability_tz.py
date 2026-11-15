from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.tests.test_integration_ingest import auth_headers, create_clinic_and_key, sample_payload


def test_appointment_times_stored_utc_displayed_clinic_tz(client, owner_a_id):
    token, clinic, key = create_clinic_and_key(client, owner_a_id)
    assert clinic["timezone"] == "Asia/Kolkata"

    ingest = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(),
    )
    customer_id = ingest.json()["customer_id"]
    service = client.post(
        "/v1/services",
        headers=auth_headers(token),
        json={"name": "Consultation", "category": "General", "duration_minutes": 30},
    ).json()
    window = client.post(
        "/v1/availability",
        headers=auth_headers(token),
        json={"weekday": 0, "start_minute": 10 * 60, "end_minute": 18 * 60},
    )
    assert window.status_code == 201

    starts_utc = datetime(2026, 12, 7, 4, 30, tzinfo=timezone.utc)  # Monday 04:30 UTC = 10:00 IST
    created = client.post(
        "/v1/appointments",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "service_id": service["id"],
            "starts_at_utc": starts_utc.isoformat().replace("+00:00", "Z"),
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["clinic_timezone"] == "Asia/Kolkata"
    assert body["starts_at_utc"].startswith("2026-12-07T04:30:00")
    local = starts_utc.astimezone(ZoneInfo("Asia/Kolkata"))
    assert "10:00" in body["starts_at_clinic"]
    assert local.strftime("%Y-%m-%d") in body["starts_at_clinic"]

    check = client.get(
        "/v1/availability/check",
        headers=auth_headers(token),
        params={
            "service_id": service["id"],
            "starts_at_utc": (starts_utc + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        },
    )
    assert check.status_code == 200
    assert check.json()["available"] is True
    assert check.json()["clinic_timezone"] == "Asia/Kolkata"
