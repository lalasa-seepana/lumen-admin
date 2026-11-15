from __future__ import annotations

from app.tests.conftest import make_token
from app.tests.test_integration_ingest import auth_headers


def test_voice_status_lists_blockers(client):
    response = client.get("/v1/voice/status")
    assert response.status_code == 200
    body = response.json()
    assert body["languages"] == ["en-IN", "hi-IN", "te-IN"]
    assert "GNANI_API_KEY (D03)" in body["blockers"]
    assert body["speech_live"] is False
    assert body["mode"] == "demo"
    assert body["evon_hf_repo_id"] == "gnani/gnani-evon-v3.3-30B-A3B"
    assert body["llm_provider"] == "none"
    assert any("OpenAI" in item or "LLM_BASE_URL" in item for item in body["blockers"])


def test_voice_status_speech_only_without_llm(client):
    from app.core.config import Settings, get_settings
    from app.main import app
    from app.tests.conftest import INTEGRATION_PEPPER, JWT_SECRET

    speech_settings = Settings(
        SUPABASE_JWT_SECRET=JWT_SECRET,
        SUPABASE_URL="https://example.supabase.co",
        LALA_CORS_ORIGINS="http://localhost:3001",
        LALA_DEFAULT_TIMEZONE="Asia/Kolkata",
        LALA_INTEGRATION_KEY_PEPPER=INTEGRATION_PEPPER,
        GNANI_API_KEY="test-gnani-key-not-paste",
        LLM_BASE_URL="",
    )
    app.dependency_overrides[get_settings] = lambda: speech_settings
    response = client.get("/v1/voice/status")
    assert response.status_code == 200
    body = response.json()
    assert body["gnani_configured"] is True
    assert body["llm_configured"] is False
    assert body["speech_live"] is True
    assert body["ready_for_live"] is False
    assert body["mode"] == "speech_only"


def test_voice_status_openai_plus_gnani_is_live_ready(client):
    from app.core.config import Settings, get_settings
    from app.main import app
    from app.tests.conftest import INTEGRATION_PEPPER, JWT_SECRET

    live_settings = Settings(
        SUPABASE_JWT_SECRET=JWT_SECRET,
        SUPABASE_URL="https://example.supabase.co",
        LALA_CORS_ORIGINS="http://localhost:3001",
        LALA_DEFAULT_TIMEZONE="Asia/Kolkata",
        LALA_INTEGRATION_KEY_PEPPER=INTEGRATION_PEPPER,
        GNANI_API_KEY="test-gnani-key-not-paste",
        LLM_BASE_URL="https://api.openai.com",
        LLM_MODEL="gpt-4o-mini",
        LLM_API_KEY="sk-test-not-real",
    )
    app.dependency_overrides[get_settings] = lambda: live_settings
    response = client.get("/v1/voice/status")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "configured"
    assert body["ready_for_live"] is True
    assert body["llm_provider"] == "openai"
    assert body["llm_model"] == "gpt-4o-mini"
    assert body["blockers"] == []


def test_openai_url_without_key_not_configured(client):
    from app.core.config import Settings, get_settings
    from app.main import app
    from app.tests.conftest import INTEGRATION_PEPPER, JWT_SECRET

    partial = Settings(
        SUPABASE_JWT_SECRET=JWT_SECRET,
        SUPABASE_URL="https://example.supabase.co",
        LALA_CORS_ORIGINS="http://localhost:3001",
        LALA_DEFAULT_TIMEZONE="Asia/Kolkata",
        LALA_INTEGRATION_KEY_PEPPER=INTEGRATION_PEPPER,
        LLM_BASE_URL="https://api.openai.com",
        LLM_API_KEY="",
    )
    app.dependency_overrides[get_settings] = lambda: partial
    body = client.get("/v1/voice/status").json()
    assert body["llm_configured"] is False
    assert body["llm_provider"] == "openai"
    assert any("LLM_API_KEY" in item for item in body["blockers"])


def test_create_voice_session_and_list_handovers(client, owner_a_id):
    token = make_token(owner_a_id)
    clinic = client.post(
        "/v1/clinics",
        headers=auth_headers(token),
        json={"name": "Voice Demo Clinic"},
    )
    assert clinic.status_code == 201

    created = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token),
        json={"language": "hi-IN", "recording_consent": False},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["language"] == "hi-IN"
    assert body["recording_consent"] is False
    assert body["ws_path"].startswith("/v1/voice/ws/")

    handovers = client.get("/v1/voice/handovers", headers=auth_headers(token))
    assert handovers.status_code == 200
    assert handovers.json() == []
