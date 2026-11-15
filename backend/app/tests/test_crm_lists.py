from __future__ import annotations

from uuid import uuid4

from app.tests.conftest import make_token
from app.tests.test_integration_ingest import auth_headers, create_clinic_and_key, sample_payload


def test_crm_lists_empty_clinic(client, owner_a_id):
    token, clinic, _created = create_clinic_and_key(client, owner_a_id)
    overview = client.get("/v1/overview", headers=auth_headers(token))
    assert overview.status_code == 200
    body = overview.json()
    assert body["clinic_id"] == clinic["id"]
    assert body["clinic_name"] == "Demo Clinic A"
    assert body["consultations_count"] == 0
    assert body["customers_count"] == 0

    assert client.get("/v1/consultations", headers=auth_headers(token)).json() == []
    assert client.get("/v1/customers", headers=auth_headers(token)).json() == []
    assert client.get("/v1/activity", headers=auth_headers(token)).json() == []


def test_crm_lists_after_ingest_and_isolation(client, owner_a_id, owner_b_id):
    token_a, clinic_a, key_a = create_clinic_and_key(client, owner_a_id, clinic_name="Demo Clinic A")
    token_b, _clinic_b, _key_b = create_clinic_and_key(client, owner_b_id, clinic_name="Demo Clinic B")

    ingest = client.post(
        "/v1/integrations/website/consultations",
        headers={
            "Authorization": f"Bearer {key_a['api_key']}",
            "Idempotency-Key": str(uuid4()),
        },
        json=sample_payload(full_name="DEMO-Asha Rao"),
    )
    assert ingest.status_code == 201
    customer_id = ingest.json()["customer_id"]

    consultations = client.get("/v1/consultations", headers=auth_headers(token_a)).json()
    assert len(consultations) == 1
    assert consultations[0]["customer_name"] == "DEMO-Asha Rao"
    assert consultations[0]["clinic_id"] == clinic_a["id"]

    customers = client.get("/v1/customers", headers=auth_headers(token_a)).json()
    assert len(customers) == 1
    assert customers[0]["consultation_count"] == 1

    detail = client.get(f"/v1/customers/{customer_id}", headers=auth_headers(token_a))
    assert detail.status_code == 200
    assert len(detail.json()["consultations"]) == 1

    activity = client.get("/v1/activity", headers=auth_headers(token_a)).json()
    assert len(activity) == 1
    assert activity[0]["action"] == "consultation.accepted"
    assert "api_key" not in str(activity)

    overview = client.get("/v1/overview", headers=auth_headers(token_a)).json()
    assert overview["consultations_count"] == 1
    assert overview["customers_count"] == 1
    assert overview["activity_count"] == 1

    # Clinic B sees none of A's data
    assert client.get("/v1/consultations", headers=auth_headers(token_b)).json() == []
    assert client.get("/v1/customers", headers=auth_headers(token_b)).json() == []
    assert client.get("/v1/activity", headers=auth_headers(token_b)).json() == []
    denied = client.get(f"/v1/customers/{customer_id}", headers=auth_headers(token_b))
    assert denied.status_code == 404


def test_crm_requires_auth(client):
    assert client.get("/v1/consultations").status_code == 401
    assert client.get("/v1/overview").status_code == 401
    assert client.get(f"/v1/customers/{uuid4()}", headers=auth_headers(make_token(uuid4()))).status_code == 403
