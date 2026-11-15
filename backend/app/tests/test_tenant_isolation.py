"""Epic 8 — dual-clinic tenant isolation suite (Milestone D).

Clinic B must never read Clinic A customers, consultations, appointments,
conversations, handovers, or inflated overview/analytics counts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.tests.conftest import make_token
from app.tests.test_integration_ingest import auth_headers, create_clinic_and_key, sample_payload


def test_clinic_b_cannot_read_clinic_a_crm(client, owner_a_id, owner_b_id):
    token_a, clinic_a, key_a = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    token_b, clinic_b, _key_b = create_clinic_and_key(client, owner_b_id, clinic_name="Demo Clinic B")

    ingest = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key_a['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(full_name="DEMO-Asha Rao", email="demo-asha@example.com"),
    )
    assert ingest.status_code == 201
    customer_id = ingest.json()["customer_id"]

    assert client.get("/v1/consultations", headers=auth_headers(token_a)).json()
    assert client.get("/v1/consultations", headers=auth_headers(token_b)).json() == []
    assert client.get("/v1/customers", headers=auth_headers(token_b)).json() == []
    assert client.get("/v1/activity", headers=auth_headers(token_b)).json() == []
    assert client.get(f"/v1/customers/{customer_id}", headers=auth_headers(token_b)).status_code == 404

    overview_b = client.get("/v1/overview", headers=auth_headers(token_b)).json()
    assert overview_b["clinic_id"] == clinic_b["id"]
    assert overview_b["consultations_count"] == 0
    assert overview_b["customers_count"] == 0
    assert overview_b["clinic_id"] != clinic_a["id"]


def test_clinic_b_cannot_read_clinic_a_appointments_or_voice(client, owner_a_id, owner_b_id, store):
    token_a, clinic_a, key_a = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    token_b, _clinic_b, _key_b = create_clinic_and_key(client, owner_b_id, clinic_name="Demo Clinic B")
    clinic_a_id = UUID(clinic_a["id"])

    ingest = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key_a['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(full_name="DEMO-Asha Rao", email="demo-asha@example.com"),
    )
    customer_id = UUID(ingest.json()["customer_id"])

    service = client.post(
        "/v1/services",
        headers=auth_headers(token_a),
        json={
            "name": "Aroma Swedish Massage",
            "category": "Heal Your Mind",
            "duration_minutes": 60,
        },
    )
    assert service.status_code == 201
    from app.tests.conftest import add_weekday_window
    from zoneinfo import ZoneInfo

    add_weekday_window(client, token_a)
    ist = ZoneInfo("Asia/Kolkata")
    starts_local = (datetime.now(timezone.utc).astimezone(ist) + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    starts = starts_local.astimezone(timezone.utc)
    appointment = client.post(
        "/v1/appointments",
        headers=auth_headers(token_a),
        json={
            "customer_id": str(customer_id),
            "service_id": service.json()["id"],
            "starts_at_utc": starts.isoformat().replace("+00:00", "Z"),
        },
    )
    assert appointment.status_code == 201

    session = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token_a),
        json={"language": "en-IN", "recording_consent": True},
    )
    assert session.status_code == 201
    conversation = store.get_conversation_by_session(UUID(session.json()["id"]))
    assert conversation is not None
    store.append_conversation_turn(
        conversation_id=conversation.id,
        clinic_id=clinic_a_id,
        role="user",
        text="What services do you offer?",
    )
    handover = store.create_handover(
        clinic_id=clinic_a_id,
        voice_session_id=conversation.voice_session_id,
        reason="unspecified",
        summary="Needs staff",
        conversation_id=conversation.id,
    )

    # B cannot see A's conversations / handovers / analytics appointments.
    assert client.get("/v1/conversations", headers=auth_headers(token_b)).json() == []
    assert client.get("/v1/handovers", headers=auth_headers(token_b)).json() == []
    denied_conv = client.get(
        f"/v1/conversations/{conversation.id}", headers=auth_headers(token_b)
    )
    assert denied_conv.status_code == 404
    denied_hand = client.patch(
        f"/v1/handovers/{handover.id}",
        headers=auth_headers(token_b),
        json={"status": "acked"},
    )
    assert denied_hand.status_code == 404

    analytics_a = client.get("/v1/analytics", headers=auth_headers(token_a)).json()
    analytics_b = client.get("/v1/analytics", headers=auth_headers(token_b)).json()
    assert analytics_a["appointments_count"] == 1
    assert analytics_a["conversations_count"] == 1
    assert analytics_a["open_handovers_count"] == 1
    assert analytics_b["appointments_count"] == 0
    assert analytics_b["conversations_count"] == 0
    assert analytics_b["open_handovers_count"] == 0
    assert client.get("/v1/appointments", headers=auth_headers(token_b)).json() == []
    assert appointment.json()["id"]


def test_clinic_b_key_cannot_ingest_into_clinic_a_namespace(client, owner_a_id, owner_b_id):
    _token_a, clinic_a, key_a = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    token_b, clinic_b, key_b = create_clinic_and_key(client, owner_b_id, clinic_name="Demo Clinic B")

    ingest_b = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key_b['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(full_name="DEMO-Bala Nair", email="demo-bala@example.com"),
    )
    assert ingest_b.status_code == 201
    assert ingest_b.json()["status"] == "accepted"

    # A's key still only writes to A; B list stays B-only.
    client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key_a['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(full_name="DEMO-Asha Rao", email="demo-asha@example.com"),
    )

    customers_b = client.get("/v1/customers", headers=auth_headers(token_b)).json()
    assert len(customers_b) == 1
    assert customers_b[0]["full_name"] == "DEMO-Bala Nair"
    assert customers_b[0]["clinic_id"] == clinic_b["id"]
    assert customers_b[0]["clinic_id"] != clinic_a["id"]


def test_unauthenticated_analytics_denied(client):
    assert client.get("/v1/analytics").status_code == 401
    assert client.get("/v1/analytics", headers=auth_headers(make_token(uuid4()))).status_code == 403
