from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.services.clinic_store import InMemoryClinicStore, reset_clinic_store
from app.api.deps import get_store

JWT_SECRET = "test-jwt-secret-for-lala-epic1-isolation"
INTEGRATION_PEPPER = "test-integration-pepper-for-lala-epic2"


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        SUPABASE_JWT_SECRET=JWT_SECRET,
        SUPABASE_URL="https://example.supabase.co",
        LALA_CORS_ORIGINS="http://localhost:3001",
        LALA_DEFAULT_TIMEZONE="Asia/Kolkata",
        LALA_INTEGRATION_KEY_PEPPER=INTEGRATION_PEPPER,
        LALA_VOICE_RETENTION_DAYS=90,
        # Keep voice status tests deterministic even if developer .env has live keys.
        GNANI_API_KEY="",
        LLM_BASE_URL="",
    )


@pytest.fixture()
def store() -> InMemoryClinicStore:
    return reset_clinic_store()


@pytest.fixture()
def client(settings: Settings, store: InMemoryClinicStore):
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_token(
    user_id: UUID,
    *,
    email: str = "owner@example.com",
    secret: str = JWT_SECRET,
    expired: bool = False,
    audience: str = "authenticated",
) -> str:
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=5) if expired else now + timedelta(hours=1)
    payload: Dict = {
        "sub": str(user_id),
        "email": email,
        "role": "authenticated",
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture()
def owner_a_id() -> UUID:
    return uuid4()


@pytest.fixture()
def owner_b_id() -> UUID:
    return uuid4()


def add_weekday_window(client, token, *, weekday: int = 0, start: int = 9 * 60, end: int = 18 * 60):
    """Add a default Monday 09:00–18:00 clinic-local availability window."""
    from app.tests.test_integration_ingest import auth_headers

    response = client.post(
        "/v1/availability",
        headers=auth_headers(token),
        json={"weekday": weekday, "start_minute": start, "end_minute": end},
    )
    assert response.status_code == 201
    return response.json()
