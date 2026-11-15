from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, StoreDep
from app.models.website import (
    DraftReviewRequest,
    ServiceImportDraftOut,
    WebsiteImportRequest,
    WebsiteKnowledgeOut,
)
from app.services import website_import as website_service

router = APIRouter(prefix="/v1/website", tags=["website"])


@router.get("/knowledge", response_model=WebsiteKnowledgeOut)
def get_knowledge(user: CurrentUser, store: StoreDep) -> WebsiteKnowledgeOut:
    return website_service.get_knowledge(store, user_id=user.id)


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
def start_import(body: WebsiteImportRequest, user: CurrentUser, store: StoreDep) -> dict:
    return website_service.import_website(store, user_id=user.id, body=body)


@router.get("/drafts", response_model=List[ServiceImportDraftOut])
def list_drafts(user: CurrentUser, store: StoreDep) -> List[ServiceImportDraftOut]:
    return website_service.list_drafts(store, user_id=user.id)


@router.post("/drafts/{draft_id}/review", response_model=ServiceImportDraftOut)
def review_draft(
    draft_id: UUID, body: DraftReviewRequest, user: CurrentUser, store: StoreDep
) -> ServiceImportDraftOut:
    return website_service.review_draft(store, user_id=user.id, draft_id=draft_id, body=body)