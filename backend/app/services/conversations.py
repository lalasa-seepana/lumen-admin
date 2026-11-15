from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import Settings
from app.models.conversations import (
    ConversationDetail,
    ConversationListItem,
    ConversationTurnOut,
    RetentionPurgeResult,
)
from app.models.voice import HandoverOut
from app.services import appointments as appointment_service
from app.services import clinics as clinic_service
from app.services.clinic_store import ClinicStore
from app.services.voice_pipeline import VoiceTurnResult


def _list_item(store: ClinicStore, row) -> ConversationListItem:
    turns = store.list_conversation_turns(row.id) if row.recording_consent and row.deleted_at is None else []
    handovers = [
        h
        for h in store.list_handovers(row.clinic_id)
        if h.conversation_id == row.id or h.voice_session_id == row.voice_session_id
    ]
    appointments = store.list_appointments_for_voice_session(
        row.clinic_id, row.voice_session_id, include_cancelled=False
    )
    return ConversationListItem(
        id=row.id,
        clinic_id=row.clinic_id,
        voice_session_id=row.voice_session_id,
        language=row.language,
        recording_consent=row.recording_consent,
        transcript_available=bool(row.recording_consent and row.deleted_at is None),
        retention_until=row.retention_until,
        deleted_at=row.deleted_at,
        turn_count=len(turns),
        handover_count=len(handovers),
        appointment_count=len(appointments),
        created_at=row.created_at,
        closed_at=row.closed_at,
    )


def ensure_conversation_for_session(
    store: ClinicStore, settings: Settings, *, voice_session_id: UUID
):
    session = store.get_voice_session(voice_session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": "Voice session not found"},
        )
    existing = store.get_conversation_by_session(voice_session_id)
    if existing is not None:
        return existing
    retention_until = datetime.now(timezone.utc) + timedelta(days=settings.voice_retention_days)
    return store.create_conversation(
        clinic_id=session.clinic_id,
        voice_session_id=session.id,
        language=session.language,
        recording_consent=session.recording_consent,
        retention_until=retention_until,
    )


def sync_session_consent(
    store: ClinicStore,
    settings: Settings,
    *,
    voice_session_id: UUID,
    recording_consent: bool,
) -> None:
    """Apply mid-session consent changes. Withdrawal stops future retention immediately."""
    conversation = store.get_conversation_by_session(voice_session_id)
    if conversation is None:
        if recording_consent:
            ensure_conversation_for_session(store, settings, voice_session_id=voice_session_id)
        return
    retention_until = conversation.retention_until
    if recording_consent and not conversation.recording_consent:
        retention_until = datetime.now(timezone.utc) + timedelta(days=settings.voice_retention_days)
    store.update_conversation_consent(
        conversation.id,
        recording_consent=recording_consent,
        retention_until=retention_until,
    )


def persist_turn_if_consented(
    store: ClinicStore,
    settings: Settings,
    *,
    voice_session_id: UUID,
    result: VoiceTurnResult,
) -> None:
    """Store transcript text only when recording_consent is true on the live session.

    Mid-session consent withdrawal is respected: earlier turns stay; new turns are not stored.
    Never store audio without consent.
    """
    session = store.get_voice_session(voice_session_id)
    if session is None or not session.recording_consent:
        return
    if not result.user_text and not result.assistant_text:
        return
    conversation = ensure_conversation_for_session(store, settings, voice_session_id=voice_session_id)
    if conversation.deleted_at is not None:
        return
    if not conversation.recording_consent:
        return
    if result.user_text:
        store.append_conversation_turn(
            conversation_id=conversation.id,
            clinic_id=conversation.clinic_id,
            role="user",
            text=result.user_text,
            has_audio_blob=False,
            audio_storage_key=None,
        )
    if result.assistant_text:
        # Audio bytes stay out of store without a consented storage backend (POC: metadata only).
        store.append_conversation_turn(
            conversation_id=conversation.id,
            clinic_id=conversation.clinic_id,
            role="assistant",
            text=result.assistant_text,
            has_audio_blob=False,
            audio_storage_key=None,
        )


def link_handover_conversation(
    store: ClinicStore, settings: Settings, *, voice_session_id: Optional[UUID], handover_id: UUID
) -> None:
    if voice_session_id is None:
        return
    conversation = ensure_conversation_for_session(store, settings, voice_session_id=voice_session_id)
    store.set_handover_conversation(handover_id, conversation.id)


def list_conversations(store: ClinicStore, *, user_id: UUID) -> List[ConversationListItem]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    rows = store.list_conversations(clinic.id, include_deleted=False)
    return [_list_item(store, row) for row in rows]


def get_conversation(store: ClinicStore, *, user_id: UUID, conversation_id: UUID) -> ConversationDetail:
    clinic, _ = clinic_service.require_membership(store, user_id)
    row = store.get_conversation(conversation_id)
    if row is None or row.clinic_id != clinic.id or row.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "conversation_not_found", "message": "Conversation not found"},
        )
    base = _list_item(store, row)
    turns: List[ConversationTurnOut] = []
    if base.transcript_available:
        turns = [
            ConversationTurnOut(
                id=turn.id,
                sequence=turn.sequence,
                role=turn.role,  # type: ignore[arg-type]
                text=turn.text,
                has_audio_blob=turn.has_audio_blob,
                created_at=turn.created_at,
            )
            for turn in store.list_conversation_turns(row.id)
        ]
    appointments = [
        appointment_service._appointment_out(store, clinic, appt)
        for appt in store.list_appointments_for_voice_session(
            clinic.id, row.voice_session_id, include_cancelled=True
        )
    ]
    return ConversationDetail(**base.model_dump(), turns=turns, appointments=appointments)


def delete_conversation(store: ClinicStore, *, user_id: UUID, conversation_id: UUID) -> ConversationDetail:
    clinic, _ = clinic_service.require_membership(store, user_id)
    row = store.get_conversation(conversation_id)
    if row is None or row.clinic_id != clinic.id or row.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "conversation_not_found", "message": "Conversation not found"},
        )
    store.hard_delete_conversation(conversation_id)
    store.add_activity_event(
        clinic_id=clinic.id,
        actor_type="owner",
        action="conversation.deleted",
        entity_type="conversation",
        entity_id=conversation_id,
        payload={"reason": "deletion_on_request"},
    )
    # Return tombstone-style detail without turns.
    deleted = store.get_conversation(conversation_id)
    assert deleted is not None
    base = _list_item(store, deleted)
    return ConversationDetail(**base.model_dump(), turns=[])


def list_handovers(store: ClinicStore, *, user_id: UUID) -> List[HandoverOut]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return [
        HandoverOut(
            id=row.id,
            clinic_id=row.clinic_id,
            voice_session_id=row.voice_session_id,
            conversation_id=row.conversation_id,
            reason=row.reason,
            summary=row.summary,
            status=row.status,
            created_at=row.created_at,
            callback_contact=row.callback_contact,
        )
        for row in store.list_handovers(clinic.id)
    ]


def update_handover(
    store: ClinicStore, *, user_id: UUID, handover_id: UUID, status_value: str
) -> HandoverOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    try:
        row = store.update_handover_status(
            clinic_id=clinic.id, handover_id=handover_id, status=status_value
        )
    except ValueError as exc:
        code = str(exc)
        if code == "handover_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "handover_not_found", "message": "Handover not found"},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_handover_status", "message": "Invalid handover status"},
        ) from exc
    store.add_activity_event(
        clinic_id=clinic.id,
        actor_type="owner",
        action="handover.updated",
        entity_type="handover",
        entity_id=row.id,
        payload={"status": row.status},
    )
    return HandoverOut(
        id=row.id,
        clinic_id=row.clinic_id,
        voice_session_id=row.voice_session_id,
        conversation_id=row.conversation_id,
        reason=row.reason,
        summary=row.summary,
        status=row.status,
        created_at=row.created_at,
        callback_contact=row.callback_contact,
    )


def purge_expired_conversations(
    store: ClinicStore, settings: Settings, *, user_id: UUID
) -> RetentionPurgeResult:
    clinic, _ = clinic_service.require_membership(store, user_id)
    cutoff = datetime.now(timezone.utc)
    purged = store.purge_expired_conversations(clinic_id=clinic.id, cutoff=cutoff)
    store.add_activity_event(
        clinic_id=clinic.id,
        actor_type="owner",
        action="conversation.retention_purged",
        entity_type="clinic",
        entity_id=clinic.id,
        payload={"conversations_purged": purged[0], "turns_purged": purged[1]},
    )
    return RetentionPurgeResult(
        retention_days=settings.voice_retention_days,
        conversations_purged=purged[0],
        turns_purged=purged[1],
        cutoff=cutoff,
    )
