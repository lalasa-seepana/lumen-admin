from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.models.visitor import VisitorSessionCreate, VisitorSessionOut
from app.services import conversations as conversation_service
from app.services.clinic_store import ClinicStore
from app.core.config import Settings


def create_public_session(
    store: ClinicStore, settings: Settings, *, body: VisitorSessionCreate
) -> VisitorSessionOut:
    if body.clinic_id is None and not body.clinic_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "clinic_required", "message": "Provide clinic_id or clinic_slug"},
        )
    record = None
    if body.clinic_id is not None:
        record = store.get_clinic(body.clinic_id)
    elif body.clinic_slug:
        record = store.get_clinic_by_slug(body.clinic_slug)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "clinic_not_found", "message": "Clinic not found"},
        )
    from app.services.voice_tools import CONSENT_TEXT_VERSION

    session = store.create_voice_session(
        clinic_id=record.id,
        language=body.language,
        recording_consent=body.recording_consent,
        actor_type="visitor",
        consent_version=CONSENT_TEXT_VERSION if body.recording_consent else None,
    )
    conversation_service.ensure_conversation_for_session(store, settings, voice_session_id=session.id)
    token = session.visitor_token or ""
    return VisitorSessionOut(
        id=session.id,
        clinic_id=session.clinic_id,
        clinic_name=record.name,
        public_slug=record.public_slug,
        language=session.language,
        recording_consent=session.recording_consent,
        status=session.status,
        created_at=session.created_at,
        visitor_token=token,
        ws_path=f"/v1/voice/ws/{session.id}",
        ai_disclosure=(
            f"You are chatting with Rhea, an AI receptionist for {record.name}, not a clinician."
        ),
    )