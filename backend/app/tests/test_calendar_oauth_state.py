from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services import calendar_connection as calendar_service
from app.services.clinic_store import InMemoryClinicStore


@pytest.fixture()
def store_with_clinic() -> tuple[InMemoryClinicStore, object]:
    store = InMemoryClinicStore()
    owner = uuid4()
    clinic, _ = store.create_clinic_for_owner(user_id=owner, name="Test Clinic", timezone_name="Asia/Kolkata")
    return store, clinic


def test_google_callback_without_stored_state_does_not_connect(store_with_clinic):
    store, clinic = store_with_clinic
    settings = Settings(
        SUPABASE_JWT_SECRET="x",
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        LALA_INTEGRATION_KEY_PEPPER="test-pepper-long-enough",
    )
    with pytest.raises(HTTPException) as exc:
        calendar_service.google_oauth_callback(
            store, settings, code="fake-auth-code", state="unknown-state-token"
        )
    assert exc.value.status_code == 400
    updated = store.get_clinic(clinic.id)
    assert updated is not None
    assert updated.google_refresh_token_enc is None
    assert updated.google_status == "disconnected"


def test_google_callback_rejects_empty_code_with_valid_state(store_with_clinic):
    store, clinic = store_with_clinic
    owner = store.list_memberships_for_clinic(clinic.id)[0].user_id
    settings = Settings(
        SUPABASE_JWT_SECRET="x",
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        LALA_INTEGRATION_KEY_PEPPER="test-pepper-long-enough",
    )
    state = "signed-state-value"
    from datetime import datetime, timedelta, timezone

    store.save_oauth_state(
        state=state,
        clinic_id=clinic.id,
        user_id=owner,
        provider="google",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    with pytest.raises(HTTPException) as exc:
        calendar_service.google_oauth_callback(store, settings, code="", state=state)
    assert exc.value.detail["code"] == "missing_code"
    updated = store.get_clinic(clinic.id)
    assert updated is not None
    assert updated.google_refresh_token_enc is None


def test_start_oauth_stores_state(store_with_clinic):
    store, clinic = store_with_clinic
    owner = store.list_memberships_for_clinic(clinic.id)[0].user_id
    settings = Settings(
        SUPABASE_JWT_SECRET="x",
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
    )
    result = calendar_service.start_google_oauth(store, settings, user_id=owner)
    assert result.get("authorize_url")
    assert len(store.oauth_states) == 1
    only = next(iter(store.oauth_states.values()))
    assert only.clinic_id == clinic.id
    assert only.user_id == owner