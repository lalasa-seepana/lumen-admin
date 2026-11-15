from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import HTTPException, status

from app.models.crm import (
    ActivityEventOut,
    AnalyticsOut,
    ConsultationListItem,
    CustomerDetail,
    CustomerListItem,
    OverviewOut,
)
from app.services import clinics as clinic_service
from app.services.clinic_store import ClinicStore, ConsultationRecord, CustomerRecord


def _consultation_item(store: ClinicStore, row: ConsultationRecord) -> ConsultationListItem:
    customer = store.get_customer(row.clinic_id, row.customer_id)
    return ConsultationListItem(
        id=row.id,
        clinic_id=row.clinic_id,
        customer_id=row.customer_id,
        customer_name=customer.full_name if customer else "Unknown",
        customer_email=customer.email_normalized if customer else "",
        category=row.category,
        service_name=row.service_name,
        source_website=row.source_website,
        created_at=row.created_at,
    )


def _customer_item(store: ClinicStore, row: CustomerRecord) -> CustomerListItem:
    count = len(store.list_consultations_for_customer(row.clinic_id, row.id))
    return CustomerListItem(
        id=row.id,
        clinic_id=row.clinic_id,
        email_normalized=row.email_normalized,
        full_name=row.full_name,
        phone_e164=row.phone_e164,
        possible_phone_duplicate=row.possible_phone_duplicate,
        created_at=row.created_at,
        consultation_count=count,
    )


def list_consultations(store: ClinicStore, *, user_id: UUID) -> List[ConsultationListItem]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return [_consultation_item(store, row) for row in store.list_consultations(clinic.id)]


def list_customers(store: ClinicStore, *, user_id: UUID) -> List[CustomerListItem]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return [_customer_item(store, row) for row in store.list_customers(clinic.id)]


def get_customer(store: ClinicStore, *, user_id: UUID, customer_id: UUID) -> CustomerDetail:
    clinic, _ = clinic_service.require_membership(store, user_id)
    row = store.get_customer(clinic.id, customer_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "customer_not_found", "message": "Customer not found"},
        )
    base = _customer_item(store, row)
    consultations = [
        _consultation_item(store, item)
        for item in store.list_consultations_for_customer(clinic.id, customer_id)
    ]
    return CustomerDetail(**base.model_dump(), consultations=consultations)


def list_activity(store: ClinicStore, *, user_id: UUID) -> List[ActivityEventOut]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return [
        ActivityEventOut(
            id=row.id,
            clinic_id=row.clinic_id,
            actor_type=row.actor_type,  # type: ignore[arg-type]
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            payload=row.payload,
            created_at=row.created_at,
        )
        for row in store.list_activity_events(clinic.id)
    ]


def overview(store: ClinicStore, *, user_id: UUID) -> OverviewOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    active_integrations = [
        row for row in store.list_website_integrations(clinic.id) if row.revoked_at is None
    ]
    return OverviewOut(
        clinic_id=clinic.id,
        clinic_name=clinic.name,
        consultations_count=len(store.list_consultations(clinic.id)),
        customers_count=len(store.list_customers(clinic.id)),
        integrations_active_count=len(active_integrations),
        activity_count=len(store.list_activity_events(clinic.id)),
    )


def analytics(store: ClinicStore, *, user_id: UUID) -> AnalyticsOut:
    """Epic 8 / D12 — enquiry + appointment (+ voice) counts from real store rows only."""
    clinic, _ = clinic_service.require_membership(store, user_id)
    active_integrations = [
        row for row in store.list_website_integrations(clinic.id) if row.revoked_at is None
    ]
    appointments = [
        row for row in getattr(store, "appointments", {}).values() if row.clinic_id == clinic.id
    ]
    open_handovers = [
        row
        for row in store.list_handovers(clinic.id)
        if row.status == "open"
    ]
    conversations = store.list_conversations(clinic.id, include_deleted=False)
    return AnalyticsOut(
        clinic_id=clinic.id,
        clinic_name=clinic.name,
        consultations_count=len(store.list_consultations(clinic.id)),
        customers_count=len(store.list_customers(clinic.id)),
        appointments_count=len(appointments),
        open_handovers_count=len(open_handovers),
        conversations_count=len(conversations),
        integrations_active_count=len(active_integrations),
        activity_count=len(store.list_activity_events(clinic.id)),
        source="clinic_store_aggregates",
    )
