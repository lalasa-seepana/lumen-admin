"""Epic 8 — end-to-end website → Clinic Dial ingest path (Milestone D).

Covers: clinic onboarding → integration key → website POST → CRM lists →
overview counts matching store aggregates (no fiction).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.tests.conftest import make_token
from app.tests.test_integration_ingest import auth_headers, create_clinic_and_key, sample_payload


def test_e2e_lumen_style_ingest_to_dashboard_counts(client, owner_a_id, store):
    token, clinic, key = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    clinic_id = UUID(clinic["id"])
    idem = str(uuid4())
    payload = sample_payload(full_name="DEMO-Asha Rao", email="demo-asha@example.com")
    headers = {
        "Authorization": f"Bearer {key['api_key']}",
        "Idempotency-Key": idem,
    }

    ingest = client.post(
        "/v1/integrations/website/consultations",
        headers=headers,
        json=payload,
    )
    assert ingest.status_code == 201
    body = ingest.json()
    assert body["status"] == "accepted"
    customer_id = body["customer_id"]
    consultation_id = body["consultation_id"]

    # Replay is idempotent (Lumen retry path).
    replay = client.post(
        "/v1/integrations/website/consultations",
        headers=headers,
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.json()["consultation_id"] == consultation_id
    assert replay.json()["customer_id"] == customer_id
    assert replay.json()["status"] == "duplicate"

    consultations = client.get("/v1/consultations", headers=auth_headers(token)).json()
    assert len(consultations) == 1
    assert consultations[0]["id"] == consultation_id
    assert consultations[0]["customer_name"] == "DEMO-Asha Rao"

    customers = client.get("/v1/customers", headers=auth_headers(token)).json()
    assert len(customers) == 1
    assert customers[0]["email_normalized"] == "demo-asha@example.com"

    detail = client.get(f"/v1/customers/{customer_id}", headers=auth_headers(token)).json()
    assert len(detail["consultations"]) == 1

    overview = client.get("/v1/overview", headers=auth_headers(token)).json()
    analytics = client.get("/v1/analytics", headers=auth_headers(token)).json()

    # Counts must match in-memory store aggregates — never invented.
    assert overview["consultations_count"] == len(store.list_consultations(clinic_id))
    assert overview["customers_count"] == len(store.list_customers(clinic_id))
    assert overview["integrations_active_count"] == len(
        [row for row in store.list_website_integrations(clinic_id) if row.revoked_at is None]
    )
    assert overview["activity_count"] == len(store.list_activity_events(clinic_id))

    assert analytics["consultations_count"] == overview["consultations_count"]
    assert analytics["customers_count"] == overview["customers_count"]
    assert analytics["appointments_count"] == len(
        [row for row in store.appointments.values() if row.clinic_id == clinic_id]
    )
    assert analytics["open_handovers_count"] == 0
    assert analytics["conversations_count"] == 0
    assert analytics["source"] == "clinic_store_aggregates"


def test_e2e_second_demo_enquiry_increments_real_counts(client, owner_a_id, store):
    token, clinic, key = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    clinic_id = UUID(clinic["id"])

    for name, email in (
        ("DEMO-Asha Rao", "demo-asha@example.com"),
        ("DEMO-Bala Nair", "demo-bala@example.com"),
    ):
        response = client.post(
            "/v1/integrations/website/consultations",
            headers={
                "Authorization": f"Bearer {key['api_key']}",
                "Idempotency-Key": str(uuid4()),
            },
            json=sample_payload(full_name=name, email=email),
        )
        assert response.status_code == 201

    overview = client.get("/v1/overview", headers=auth_headers(token)).json()
    assert overview["consultations_count"] == 2
    assert overview["customers_count"] == 2
    assert overview["consultations_count"] == len(store.list_consultations(clinic_id))
    assert overview["customers_count"] == len(store.list_customers(clinic_id))


def test_e2e_enquiry_to_appointment_booking(client, owner_a_id, store):
    """Milestone B+D path: website enquiry → book from owner API → analytics."""
    from datetime import datetime, timedelta, timezone

    token, clinic, key = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    clinic_id = UUID(clinic["id"])
    ingest = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(full_name="DEMO-Asha Rao"),
    )
    customer_id = ingest.json()["customer_id"]
    service = client.post(
        "/v1/services",
        headers=auth_headers(token),
        json={"name": "Aroma Swedish Massage", "category": "Heal Your Mind", "duration_minutes": 60},
    ).json()
    from app.tests.conftest import add_weekday_window

    add_weekday_window(client, token, weekday=0, start=9 * 60, end=20 * 60)
    add_weekday_window(client, token, weekday=1, start=9 * 60, end=20 * 60)
    add_weekday_window(client, token, weekday=2, start=9 * 60, end=20 * 60)
    add_weekday_window(client, token, weekday=3, start=9 * 60, end=20 * 60)
    add_weekday_window(client, token, weekday=4, start=9 * 60, end=20 * 60)
    add_weekday_window(client, token, weekday=5, start=9 * 60, end=20 * 60)
    add_weekday_window(client, token, weekday=6, start=9 * 60, end=20 * 60)
    starts = (datetime.now(timezone.utc) + timedelta(days=3)).replace(
        hour=11, minute=0, second=0, microsecond=0
    )
    booked = client.post(
        "/v1/appointments",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "service_id": service["id"],
            "starts_at_utc": starts.isoformat().replace("+00:00", "Z"),
        },
    )
    assert booked.status_code == 201
    analytics = client.get("/v1/analytics", headers=auth_headers(token)).json()
    assert analytics["appointments_count"] == 1
    assert analytics["appointments_count"] == len(
        [row for row in store.appointments.values() if row.clinic_id == clinic_id]
    )
    assert analytics["consultations_count"] == 1
