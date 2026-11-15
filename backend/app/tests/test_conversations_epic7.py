from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.tests.conftest import make_token
from app.tests.test_integration_ingest import auth_headers


def _create_clinic(client, token, name="Conv Clinic"):
    response = client.post("/v1/clinics", headers=auth_headers(token), json={"name": name})
    assert response.status_code == 201
    return response.json()["clinic"]["id"]


def test_no_consent_stores_no_transcript_turns(client, owner_a_id, store):
    token = make_token(owner_a_id)
    _create_clinic(client, token)
    created = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token),
        json={"language": "en-IN", "recording_consent": False},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    conversation = store.get_conversation_by_session(UUID(session_id))
    assert conversation is not None
    assert conversation.recording_consent is False

    # Simulate a consented-path persist call with a fake turn — service must no-op without consent.
    from app.core.config import Settings
    from app.services.conversations import persist_turn_if_consented
    from app.services.voice_pipeline import VoiceTurnResult

    persist_turn_if_consented(
        store,
        Settings(LALA_VOICE_RETENTION_DAYS=90),
        voice_session_id=conversation.voice_session_id,
        result=VoiceTurnResult(user_text="hello", assistant_text="hi"),
    )
    assert store.list_conversation_turns(conversation.id) == []

    listed = client.get("/v1/conversations", headers=auth_headers(token))
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["transcript_available"] is False
    assert body[0]["turn_count"] == 0


def test_consent_persists_turns_and_isolation(client, owner_a_id, owner_b_id, store):
    token_a = make_token(owner_a_id, email="a@example.com")
    token_b = make_token(owner_b_id, email="b@example.com")
    _create_clinic(client, token_a, "Clinic A")
    _create_clinic(client, token_b, "Clinic B")

    created = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token_a),
        json={"language": "en-IN", "recording_consent": True},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    conversation = store.get_conversation_by_session(UUID(session_id))
    assert conversation is not None

    from app.core.config import Settings
    from app.services.conversations import persist_turn_if_consented
    from app.services.voice_pipeline import VoiceTurnResult

    persist_turn_if_consented(
        store,
        Settings(LALA_VOICE_RETENTION_DAYS=90),
        voice_session_id=conversation.voice_session_id,
        result=VoiceTurnResult(
            user_text="What services do you offer?",
            assistant_text="I'm Rhea, an AI receptionist. I can help with services and booking.",
        ),
    )

    detail = client.get(
        f"/v1/conversations/{conversation.id}", headers=auth_headers(token_a)
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["transcript_available"] is True
    assert len(body["turns"]) == 2
    assert body["turns"][0]["role"] == "user"
    assert body["turns"][0]["has_audio_blob"] is False

    denied = client.get(
        f"/v1/conversations/{conversation.id}", headers=auth_headers(token_b)
    )
    assert denied.status_code == 404


def test_handover_inbox_and_status_update(client, owner_a_id, store):
    token = make_token(owner_a_id)
    _create_clinic(client, token)
    created = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token),
        json={"language": "en-IN", "recording_consent": True},
    )
    session_id = created.json()["id"]
    conversation = store.get_conversation_by_session(UUID(session_id))

    handover = store.create_handover(
        clinic_id=conversation.clinic_id,
        voice_session_id=conversation.voice_session_id,
        reason="medical_advice_request",
        summary="Caller asked for diagnosis",
        conversation_id=conversation.id,
    )

    listed = client.get("/v1/handovers", headers=auth_headers(token))
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(handover.id)
    assert rows[0]["conversation_id"] == str(conversation.id)

    patched = client.patch(
        f"/v1/handovers/{handover.id}",
        headers=auth_headers(token),
        json={"status": "acked"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "acked"


def test_deletion_on_request_and_retention_purge(client, owner_a_id, store):
    token = make_token(owner_a_id)
    _create_clinic(client, token)
    created = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token),
        json={"language": "en-IN", "recording_consent": True},
    )
    conversation = store.get_conversation_by_session(UUID(created.json()["id"]))
    store.append_conversation_turn(
        conversation_id=conversation.id,
        clinic_id=conversation.clinic_id,
        role="user",
        text="hello",
    )

    deleted = client.delete(
        f"/v1/conversations/{conversation.id}", headers=auth_headers(token)
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None
    assert deleted.json()["turns"] == []
    assert store.list_conversation_turns(conversation.id) == []

    # Fresh consented conversation past retention window.
    created2 = client.post(
        "/v1/voice/sessions",
        headers=auth_headers(token),
        json={"language": "te-IN", "recording_consent": True},
    )
    conversation2 = store.get_conversation_by_session(UUID(created2.json()["id"]))
    store.append_conversation_turn(
        conversation_id=conversation2.id,
        clinic_id=conversation2.clinic_id,
        role="assistant",
        text="Namaskaram",
    )
    # Force expiry
    expired = store.conversations[conversation2.id]
    store.conversations[conversation2.id] = type(expired)(
        id=expired.id,
        clinic_id=expired.clinic_id,
        voice_session_id=expired.voice_session_id,
        language=expired.language,
        recording_consent=expired.recording_consent,
        retention_until=datetime.now(timezone.utc) - timedelta(days=1),
        created_at=expired.created_at,
        deleted_at=None,
        closed_at=None,
    )

    purged = client.post(
        "/v1/conversations/retention/purge", headers=auth_headers(token)
    )
    assert purged.status_code == 200
    body = purged.json()
    assert body["retention_days"] == 90
    assert body["conversations_purged"] >= 1
    assert body["turns_purged"] >= 1
    assert store.list_conversation_turns(conversation2.id) == []
