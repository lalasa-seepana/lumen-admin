from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class ConsultationListItem(BaseModel):
    id: UUID
    clinic_id: UUID
    customer_id: UUID
    customer_name: str
    customer_email: str
    category: str
    service_name: Optional[str] = None
    source_website: str
    created_at: datetime


class CustomerListItem(BaseModel):
    id: UUID
    clinic_id: UUID
    email_normalized: str
    full_name: str
    phone_e164: Optional[str] = None
    possible_phone_duplicate: bool = False
    created_at: datetime
    consultation_count: int = 0


class CustomerDetail(CustomerListItem):
    consultations: List[ConsultationListItem]


class ActivityEventOut(BaseModel):
    id: UUID
    clinic_id: UUID
    actor_type: Literal["system", "owner", "integration"]
    action: str
    entity_type: str
    entity_id: Optional[UUID] = None
    payload: Dict[str, Any]
    created_at: datetime


class OverviewOut(BaseModel):
    clinic_id: UUID
    clinic_name: str
    consultations_count: int
    customers_count: int
    integrations_active_count: int
    activity_count: int


class AnalyticsOut(BaseModel):
    """Minimal Milestone D analytics — real clinic_store aggregates only."""

    clinic_id: UUID
    clinic_name: str
    consultations_count: int
    customers_count: int
    appointments_count: int
    open_handovers_count: int
    conversations_count: int
    integrations_active_count: int
    activity_count: int
    source: str = "clinic_store_aggregates"
