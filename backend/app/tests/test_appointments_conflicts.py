from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.tests.conftest import add_weekday_window, make_token
from app.tests.test_integration_ingest import auth_headers, create_clinic_and_key, sample_payload


def _seed_customer_and_service(client, token, key):
    ingest = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(full_name="DEMO-Asha Rao", email="demo-asha@example.com"),
    )
    assert ingest.status_code == 201
    customer_id = ingest.json()["customer_id"]
    service = client.post(
        "/v1/services",
        headers=auth_headers(token),
        json={
            "name": "Aroma Swedish Massage",
            "category": "Heal Your Mind",
            "duration_minutes": 60,
        },
    )
    assert service.status_code == 201
    return customer_id, service.json()["id"]


def test_back_to_back_ok_overlap_conflict_and_cancel_frees(client, owner_a_id):
    token, _clinic, key = create_clinic_and_key(client, owner_a_id)
    customer_id, service_id = _seed_customer_and_service(client, token, key)

    add_weekday_window(client, token, weekday=0, start=10 * 60, end=18 * 60)

    ist = ZoneInfo("Asia/Kolkata")
    now_local = datetime.now(timezone.utc).astimezone(ist)
    days_ahead = (0 - now_local.weekday()) % 7
    if days_ahead == 0 and now_local.hour >= 10:
        days_ahead = 7
    monday_local = (now_local + timedelta(days=days_ahead)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    monday = monday_local.astimezone(timezone.utc)

    first = client.post(
        "/v1/appointments",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "service_id": service_id,
            "starts_at_utc": monday.isoformat().replace("+00:00", "Z"),
        },
    )
    assert first.status_code == 201
    assert first.json()["status"] == "booked"
    assert "IST" in first.json()["starts_at_clinic"] or "Asia/Kolkata" in first.json()["clinic_timezone"]

    # Back-to-back at 11:00 OK
    second_start = monday + timedelta(hours=1)
    second = client.post(
        "/v1/appointments",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "service_id": service_id,
            "starts_at_utc": second_start.isoformat().replace("+00:00", "Z"),
        },
    )
    assert second.status_code == 201

    # Overlap at 10:30 → 409
    conflict = client.post(
        "/v1/appointments",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "service_id": service_id,
            "starts_at_utc": (monday + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "appointment_conflict"

    cancelled = client.patch(
        f"/v1/appointments/{first.json()['id']}",
        headers=auth_headers(token),
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # Slot freed — 10:00 bookable again
    again = client.post(
        "/v1/appointments",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "service_id": service_id,
            "starts_at_utc": monday.isoformat().replace("+00:00", "Z"),
        },
    )
    assert again.status_code == 201

    activity = client.get("/v1/activity", headers=auth_headers(token)).json()
    actions = {row["action"] for row in activity}
    assert "appointment.created" in actions
    assert "appointment.cancelled" in actions


def test_outside_availability_rejected(client, owner_a_id):
    token, _clinic, key = create_clinic_and_key(client, owner_a_id)
    customer_id, service_id = _seed_customer_and_service(client, token, key)
    client.post(
        "/v1/availability",
        headers=auth_headers(token),
        json={"weekday": 0, "start_minute": 10 * 60, "end_minute": 12 * 60},
    )
    ist = ZoneInfo("Asia/Kolkata")
    now_local = datetime.now(timezone.utc).astimezone(ist)
    days_ahead = (0 - now_local.weekday()) % 7 or 7
    monday_late = (
        (now_local + timedelta(days=days_ahead))
        .replace(hour=15, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
    )
    response = client.post(
        "/v1/appointments",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "service_id": service_id,
            "starts_at_utc": monday_late.isoformat().replace("+00:00", "Z"),
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "outside_availability"


def test_cross_clinic_appointment_isolation(client, owner_a_id, owner_b_id):
    token_a, _clinic_a, key_a = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    token_b, _clinic_b, _key_b = create_clinic_and_key(client, owner_b_id, clinic_name="Demo Clinic B")
    customer_id, service_id = _seed_customer_and_service(client, token_a, key_a)
    ist = ZoneInfo("Asia/Kolkata")
    starts_local = (datetime.now(timezone.utc).astimezone(ist) + timedelta(days=2)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    add_weekday_window(client, token_a, weekday=starts_local.weekday())
    starts = starts_local.astimezone(timezone.utc)
    created = client.post(
        "/v1/appointments",
        headers=auth_headers(token_a),
        json={
            "customer_id": customer_id,
            "service_id": service_id,
            "starts_at_utc": starts.isoformat().replace("+00:00", "Z"),
        },
    )
    assert created.status_code == 201

    assert client.get("/v1/appointments", headers=auth_headers(token_b)).json() == []
    assert client.get("/v1/services", headers=auth_headers(token_b)).json() == []
    denied = client.patch(
        f"/v1/appointments/{created.json()['id']}",
        headers=auth_headers(token_b),
        json={"status": "cancelled"},
    )
    assert denied.status_code == 404
