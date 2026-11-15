from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.tests.conftest import make_token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def sample_payload(**overrides):
    body = {
        "external_enquiry_id": str(uuid4()),
        "full_name": "DEMO-Asha Rao",
        "email": "demo-asha@example.com",
        "phone": "+919876543210",
        "category": "Heal Your Mind",
        "service": {
            "external_id": "b1000000-0000-4000-8000-000000000001",
            "name": "Aroma Swedish Massage",
        },
        "consent": {
            "ai_call_consent": True,
            "consent_text": "I agree to receive calls from Lumen's AI receptionist about my enquiry.",
            "consent_version": "lumen-ai-calls-v1",
            "consented_at": "2026-11-10T10:30:00Z",
        },
        "source": {
            "website": "lumen",
            "submitted_at": "2026-11-10T10:30:00Z",
        },
    }
    body.update(overrides)
    return body


def create_clinic_and_key(client, owner_id, *, clinic_name="Demo Clinic A"):
    token = make_token(owner_id, email=f"{clinic_name.replace(' ', '-').lower()}@example.com")
    clinic = client.post(
        "/v1/clinics",
        headers=auth_headers(token),
        json={"name": clinic_name},
    ).json()["clinic"]
    created = client.post(
        "/v1/integrations",
        headers=auth_headers(token),
        json={"label": "Lumen website"},
    )
    assert created.status_code == 201
    body = created.json()
    assert "api_key" in body
    assert body["key_prefix"]
    assert "key_hash" not in body
    return token, clinic, body


def test_mint_key_shows_plaintext_once_and_lists_prefix_only(client, owner_a_id):
    token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    listed = client.get("/v1/integrations", headers=auth_headers(token))
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["id"] == created["id"]
    assert rows[0]["key_prefix"] == created["key_prefix"]
    assert "api_key" not in rows[0]


def test_ingest_creates_consultation_201(client, owner_a_id):
    _token, clinic, created = create_clinic_and_key(client, owner_a_id)
    idem = str(uuid4())
    response = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {created['api_key']}",
            "Idempotency-Key": idem,
        },
        json=sample_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "accepted"
    assert body["dedupe"]["customer"] == "created"
    assert body["consultation_id"]
    assert body["customer_id"]

    activity = client.get(
        "/v1/integrations/activity", headers=auth_headers(make_token(owner_a_id))
    )
    assert activity.status_code == 200
    rows = activity.json()
    assert rows[0]["status"] == "accepted"
    assert rows[0]["clinic_id"] == clinic["id"]
    assert rows[0]["idempotency_key"] == idem
    assert created["api_key"] not in str(rows)


def test_idempotency_replay_returns_200_same_ids(client, owner_a_id):
    _token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    idem = str(uuid4())
    payload = sample_payload()
    headers = {
        "Authorization": f"Bearer {created['api_key']}",
        "Idempotency-Key": idem,
    }
    first = client.post("/v1/integrations/website/consultations", headers=headers, json=payload)
    second = client.post("/v1/integrations/website/consultations", headers=headers, json=payload)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["consultation_id"] == second.json()["consultation_id"]
    assert first.json()["customer_id"] == second.json()["customer_id"]
    assert second.json()["status"] == "duplicate"

    activity = client.get(
        "/v1/integrations/activity", headers=auth_headers(make_token(owner_a_id))
    ).json()
    statuses = [row["status"] for row in activity]
    assert "accepted" in statuses
    assert "duplicate" in statuses


def test_email_match_enriches_same_customer(client, owner_a_id):
    _token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    headers_base = {"Authorization": f"Bearer {created['api_key']}"}
    first = client.post(
        "/v1/integrations/website/consultations",
        headers={**headers_base, "Idempotency-Key": str(uuid4())},
        json=sample_payload(phone=None),
    )
    second = client.post(
        "/v1/integrations/website/consultations",
        headers={**headers_base, "Idempotency-Key": str(uuid4())},
        json=sample_payload(
            external_enquiry_id=str(uuid4()),
            email="DEMO-ASHA@example.com",
            phone="+919876543210",
        ),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["customer_id"] == second.json()["customer_id"]
    assert second.json()["dedupe"]["customer"] == "existing"
    assert first.json()["consultation_id"] != second.json()["consultation_id"]


def test_revoked_key_returns_401(client, owner_a_id):
    token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    revoked = client.post(
        f"/v1/integrations/{created['id']}/revoke",
        headers=auth_headers(token),
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None

    response = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {created['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(),
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_integration_key"


def test_missing_or_wrong_key_returns_401(client, owner_a_id):
    create_clinic_and_key(client, owner_a_id)
    missing = client.post(
        "/v1/integrations/website/consultations",
        json=sample_payload(),
    )
    assert missing.status_code == 401

    wrong = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": "Bearer lala_live_deadbeef_not-a-real-key",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(),
    )
    assert wrong.status_code == 401


def test_unknown_fields_rejected_400(client, owner_a_id):
    _token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    payload = sample_payload()
    payload["unexpected"] = "nope"
    response = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {created['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=payload,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"

    activity = client.get(
        "/v1/integrations/activity", headers=auth_headers(make_token(owner_a_id))
    ).json()
    assert activity[0]["status"] == "rejected"
    assert activity[0]["reason"] == "schema_validation"


def test_missing_consent_rejected_400(client, owner_a_id):
    _token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    payload = sample_payload()
    del payload["consent"]
    response = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {created['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=payload,
    )
    assert response.status_code == 400


def test_clinic_spoof_field_rejected(client, owner_a_id):
    _token, clinic, created = create_clinic_and_key(client, owner_a_id)
    payload = sample_payload()
    payload["clinic_id"] = str(uuid4())
    response = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {created['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=payload,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "clinic_spoof_rejected"
    assert clinic["id"]  # clinic resolved from key only; spoof ignored via reject


def test_cross_clinic_key_cannot_write_other_tenant(client, owner_a_id, owner_b_id):
    _token_a, clinic_a, key_a = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    _token_b, clinic_b, key_b = create_clinic_and_key(client, owner_b_id, clinic_name="Demo Clinic B")
    assert clinic_a["id"] != clinic_b["id"]

    # Key A creates under clinic A only
    response = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key_a['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(email="only-a@example.com"),
    )
    assert response.status_code == 201

    activity_a = client.get(
        "/v1/integrations/activity", headers=auth_headers(make_token(owner_a_id))
    ).json()
    activity_b = client.get(
        "/v1/integrations/activity", headers=auth_headers(make_token(owner_b_id))
    ).json()
    assert len(activity_a) == 1
    assert activity_a[0]["clinic_id"] == clinic_a["id"]
    assert activity_b == []

    # Key B cannot see A's activity via owner B
    assert all(row["clinic_id"] == clinic_b["id"] for row in activity_b)


def test_missing_idempotency_key_400(client, owner_a_id):
    _token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    response = client.post(
        "/v1/integrations/website/consultations",
        headers={"Authorization": f"Bearer {created['api_key']}"},
        json=sample_payload(),
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "missing_idempotency_key"


def test_activity_never_contains_raw_key(client, owner_a_id):
    _token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {created['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(),
    )
    listed = client.get("/v1/integrations", headers=auth_headers(make_token(owner_a_id))).json()
    activity = client.get(
        "/v1/integrations/activity", headers=auth_headers(make_token(owner_a_id))
    ).json()
    blob = str(listed) + str(activity)
    assert created["api_key"] not in blob
    assert "key_hash" not in blob
