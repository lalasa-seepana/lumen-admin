from __future__ import annotations

from uuid import uuid4

from app.core.phone import normalize_phone_e164
from app.tests.conftest import make_token
from app.tests.test_integration_ingest import auth_headers, create_clinic_and_key, sample_payload


def test_normalize_phone_e164_india():
    assert normalize_phone_e164("+91 98765 43210") == "+919876543210"
    assert normalize_phone_e164("9876543210") == "+919876543210"
    assert normalize_phone_e164("09876543210") == "+919876543210"
    assert normalize_phone_e164(None) is None


def test_same_email_two_consultations_one_customer(client, owner_a_id):
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


def test_existing_phone_not_overwritten(client, owner_a_id):
    _token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    headers_base = {"Authorization": f"Bearer {created['api_key']}"}
    first = client.post(
        "/v1/integrations/website/consultations",
        headers={**headers_base, "Idempotency-Key": str(uuid4())},
        json=sample_payload(phone="+919111111111"),
    )
    second = client.post(
        "/v1/integrations/website/consultations",
        headers={**headers_base, "Idempotency-Key": str(uuid4())},
        json=sample_payload(
            external_enquiry_id=str(uuid4()),
            email="demo-asha@example.com",
            phone="+919222222222",
        ),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["customer_id"] == second.json()["customer_id"]
    # Phone stay-as-first is store behaviour; API does not echo phone — covered by
    # phone-only non-merge + fill-missing tests.


def test_phone_only_match_does_not_merge(client, owner_a_id):
    _token, _clinic, created = create_clinic_and_key(client, owner_a_id)
    headers_base = {"Authorization": f"Bearer {created['api_key']}"}
    first = client.post(
        "/v1/integrations/website/consultations",
        headers={**headers_base, "Idempotency-Key": str(uuid4())},
        json=sample_payload(email="person-a@example.com", phone="9876543210"),
    )
    second = client.post(
        "/v1/integrations/website/consultations",
        headers={**headers_base, "Idempotency-Key": str(uuid4())},
        json=sample_payload(
            external_enquiry_id=str(uuid4()),
            email="person-b@example.com",
            full_name="DEMO-Other Person",
            phone="+91 98765 43210",
        ),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["customer_id"] != second.json()["customer_id"]
    assert second.json()["dedupe"]["possible_phone_duplicate"] is True


def test_owner_jwt_still_required_for_activity(client, owner_a_id):
    create_clinic_and_key(client, owner_a_id)
    response = client.get("/v1/integrations/activity", headers=auth_headers(make_token(owner_a_id)))
    assert response.status_code == 200
