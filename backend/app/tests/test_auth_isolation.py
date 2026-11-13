from __future__ import annotations

from uuid import uuid4

from app.tests.conftest import make_token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_token_returns_401(client):
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_token"


def test_expired_jwt_returns_401(client, owner_a_id):
    token = make_token(owner_a_id, expired=True)
    response = client.get("/v1/me", headers=auth_headers(token))
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "token_expired"


def test_invalid_signature_returns_401(client, owner_a_id):
    token = make_token(owner_a_id, secret="wrong-secret-at-least-32-bytes-long!!")
    response = client.get("/v1/me", headers=auth_headers(token))
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_token"


def test_me_without_membership(client, owner_a_id):
    token = make_token(owner_a_id, email="demo-owner-a@example.com")
    response = client.get("/v1/me", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(owner_a_id)
    assert body["email"] == "demo-owner-a@example.com"
    assert body["clinic"] is None
    assert body["membership"] is None


def test_current_clinic_without_membership_forbidden(client, owner_a_id):
    token = make_token(owner_a_id)
    response = client.get("/v1/clinics/current", headers=auth_headers(token))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "no_clinic_membership"


def test_create_clinic_defaults_timezone_and_owner_role(client, owner_a_id):
    token = make_token(owner_a_id, email="demo-owner-a@example.com")
    response = client.post(
        "/v1/clinics",
        headers=auth_headers(token),
        json={"name": "Demo Clinic A"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["clinic"]["name"] == "Demo Clinic A"
    assert body["clinic"]["timezone"] == "Asia/Kolkata"
    assert body["membership"]["role"] == "owner"
    assert body["membership"]["user_id"] == str(owner_a_id)
    assert body["membership"]["clinic_id"] == body["clinic"]["id"]


def test_owner_cannot_create_second_clinic(client, owner_a_id):
    token = make_token(owner_a_id)
    first = client.post("/v1/clinics", headers=auth_headers(token), json={"name": "Demo Clinic A"})
    assert first.status_code == 201
    second = client.post("/v1/clinics", headers=auth_headers(token), json={"name": "Another"})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "clinic_exists"


def test_dual_clinic_isolation(client, owner_a_id, owner_b_id):
    token_a = make_token(owner_a_id, email="demo-owner-a@example.com")
    token_b = make_token(owner_b_id, email="demo-owner-b@example.com")

    clinic_a = client.post(
        "/v1/clinics", headers=auth_headers(token_a), json={"name": "Demo Clinic A"}
    ).json()["clinic"]
    clinic_b = client.post(
        "/v1/clinics", headers=auth_headers(token_b), json={"name": "Demo Clinic B"}
    ).json()["clinic"]

    assert clinic_a["id"] != clinic_b["id"]

    current_a = client.get("/v1/clinics/current", headers=auth_headers(token_a))
    current_b = client.get("/v1/clinics/current", headers=auth_headers(token_b))
    assert current_a.status_code == 200
    assert current_b.status_code == 200
    assert current_a.json()["id"] == clinic_a["id"]
    assert current_b.json()["id"] == clinic_b["id"]
    assert current_a.json()["name"] == "Demo Clinic A"
    assert current_b.json()["name"] == "Demo Clinic B"

    # Owner A cannot read clinic B by id
    denied = client.get(f"/v1/clinics/{clinic_b['id']}", headers=auth_headers(token_a))
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "clinic_forbidden"

    # Owner B cannot read clinic A by id
    denied_b = client.get(f"/v1/clinics/{clinic_a['id']}", headers=auth_headers(token_b))
    assert denied_b.status_code == 403

    # Owner A can read own clinic by id
    allowed = client.get(f"/v1/clinics/{clinic_a['id']}", headers=auth_headers(token_a))
    assert allowed.status_code == 200
    assert allowed.json()["id"] == clinic_a["id"]


def test_unknown_clinic_id_forbidden_for_member(client, owner_a_id):
    token = make_token(owner_a_id)
    client.post("/v1/clinics", headers=auth_headers(token), json={"name": "Demo Clinic A"})
    response = client.get(f"/v1/clinics/{uuid4()}", headers=auth_headers(token))
    assert response.status_code == 403
