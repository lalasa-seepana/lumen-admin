from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, StoreDep
from app.models.crm import (
    ActivityEventOut,
    AnalyticsOut,
    ConsultationListItem,
    CustomerDetail,
    CustomerListItem,
    OverviewOut,
)
from app.services import crm as crm_service

router = APIRouter(prefix="/v1", tags=["crm"])


@router.get("/overview", response_model=OverviewOut)
def get_overview(user: CurrentUser, store: StoreDep) -> OverviewOut:
    return crm_service.overview(store, user_id=user.id)


@router.get("/analytics", response_model=AnalyticsOut)
def get_analytics(user: CurrentUser, store: StoreDep) -> AnalyticsOut:
    return crm_service.analytics(store, user_id=user.id)


@router.get("/consultations", response_model=List[ConsultationListItem])
def get_consultations(user: CurrentUser, store: StoreDep) -> List[ConsultationListItem]:
    return crm_service.list_consultations(store, user_id=user.id)


@router.get("/customers", response_model=List[CustomerListItem])
def get_customers(user: CurrentUser, store: StoreDep) -> List[CustomerListItem]:
    return crm_service.list_customers(store, user_id=user.id)


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: UUID, user: CurrentUser, store: StoreDep) -> CustomerDetail:
    return crm_service.get_customer(store, user_id=user.id, customer_id=customer_id)


@router.get("/activity", response_model=List[ActivityEventOut])
def get_activity(user: CurrentUser, store: StoreDep) -> List[ActivityEventOut]:
    return crm_service.list_activity(store, user_id=user.id)
