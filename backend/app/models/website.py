from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WebsiteImportRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class WebsitePageOut(BaseModel):
    url: str
    title: str
    fetched_at: datetime


class WebsiteKnowledgeOut(BaseModel):
    website_url: Optional[str] = None
    last_import_at: Optional[datetime] = None
    last_error: Optional[str] = None
    pending_drafts: int
    pages: List[WebsitePageOut]


class ServiceImportDraftOut(BaseModel):
    id: UUID
    clinic_id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    price_paise: Optional[int] = None
    currency: Optional[str] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    imported_at: datetime
    status: Literal["pending", "approved", "rejected", "merged"]


class DraftReviewRequest(BaseModel):
    action: Literal["approve", "reject", "merge"]
    merge_into_service_id: Optional[UUID] = None
    edits: Optional[dict] = None