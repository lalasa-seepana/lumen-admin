from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SettingsDep, StoreDep
from app.models.conversations import (
    ConversationDetail,
    ConversationListItem,
    HandoverUpdate,
    RetentionPurgeResult,
)
from app.models.voice import HandoverOut
from app.services import conversations as conversation_service

router = APIRouter(prefix="/v1", tags=["conversations"])


@router.get("/conversations", response_model=List[ConversationListItem])
def get_conversations(user: CurrentUser, store: StoreDep) -> List[ConversationListItem]:
    return conversation_service.list_conversations(store, user_id=user.id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: UUID, user: CurrentUser, store: StoreDep
) -> ConversationDetail:
    return conversation_service.get_conversation(
        store, user_id=user.id, conversation_id=conversation_id
    )


@router.delete("/conversations/{conversation_id}", response_model=ConversationDetail)
def delete_conversation(
    conversation_id: UUID, user: CurrentUser, store: StoreDep
) -> ConversationDetail:
    return conversation_service.delete_conversation(
        store, user_id=user.id, conversation_id=conversation_id
    )


@router.post(
    "/conversations/retention/purge",
    response_model=RetentionPurgeResult,
    status_code=status.HTTP_200_OK,
)
def purge_retention(
    user: CurrentUser, store: StoreDep, settings: SettingsDep
) -> RetentionPurgeResult:
    """Owner-triggered retention job (POC). Deletes expired consented transcripts."""
    return conversation_service.purge_expired_conversations(
        store, settings, user_id=user.id
    )


@router.get("/handovers", response_model=List[HandoverOut])
def get_handovers(user: CurrentUser, store: StoreDep) -> List[HandoverOut]:
    return conversation_service.list_handovers(store, user_id=user.id)


@router.patch("/handovers/{handover_id}", response_model=HandoverOut)
def patch_handover(
    handover_id: UUID, body: HandoverUpdate, user: CurrentUser, store: StoreDep
) -> HandoverOut:
    return conversation_service.update_handover(
        store, user_id=user.id, handover_id=handover_id, status_value=body.status
    )
