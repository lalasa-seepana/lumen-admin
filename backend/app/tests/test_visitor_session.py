from __future__ import annotations

from uuid import UUID

from app.tests.conftest import make_token
from app.tests.test_integration_ingest import auth_headers, create_clinic_and_key


def test_visitor_session_mint_and_requires_ws_token(client, owner_a_id):
    token, clinic, _key = create_clinic_and_key(client, owner_a_id)
    onboarding = client.get("/v1/onboarding", headers=auth_headers(token)).json()
    assert onboarding["steps"]
    assert any(step["key"] == "clinic_profile" and step["status"] == "completed" for step in onboarding["steps"])

    created = client.post(
        "/v1/visitor/sessions",
        json={"clinic_id": clinic["id"], "language": "en-IN", "recording_consent": False},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["clinic_id"] == clinic["id"]
    assert body["visitor_token"]
    assert body["ws_path"].startswith("/v1/voice/ws/")

    owner_session = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token),
        json={"language": "en-IN", "recording_consent": False},
    ).json()
    assert owner_session["visitor_token"]


def test_visitor_session_unknown_clinic(client):
    response = client.post(
        "/v1/visitor/sessions",
        json={"clinic_id": str(UUID(int=0)), "language": "en-IN"},
    )
    assert response.status_code == 404