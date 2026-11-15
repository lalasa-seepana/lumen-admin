from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.integration_keys import generate_integration_key, hash_integration_key
from app.core.phone import normalize_phone_e164
from app.models.integrations import (
    DedupeOut,
    IntegrationActivityOut,
    IntegrationCreatedOut,
    IntegrationCreate,
    IntegrationOut,
    WebsiteConsultationIn,
    WebsiteConsultationOut,
)
from app.services.clinic_store import (
    ClinicStore,
    ConsultationRecord,
    WebsiteIntegrationRecord,
)
from app.services import clinics as clinic_service


def _integration_out(record: WebsiteIntegrationRecord) -> IntegrationOut:
    return IntegrationOut(
        id=record.id,
        clinic_id=record.clinic_id,
        key_prefix=record.key_prefix,
        label=record.label,
        revoked_at=record.revoked_at,
        created_at=record.created_at,
    )


def _activity_out(record) -> IntegrationActivityOut:
    return IntegrationActivityOut(
        id=record.id,
        clinic_id=record.clinic_id,
        integration_id=record.integration_id,
        status=record.status,
        reason=record.reason,
        idempotency_key=record.idempotency_key,
        created_at=record.created_at,
    )


def create_integration(
    store: ClinicStore,
    settings: Settings,
    *,
    user_id: UUID,
    body: IntegrationCreate,
) -> IntegrationCreatedOut:
    clinic, _membership = clinic_service.require_membership(store, user_id)
    pepper = settings.lala_integration_key_pepper.strip()
    if len(pepper) < 16:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "pepper_missing",
                "message": "Integration key pepper is not configured",
            },
        )
    generated = generate_integration_key(pepper)
    record = store.create_website_integration(
        clinic_id=clinic.id,
        key_hash=generated.key_hash,
        key_prefix=generated.key_prefix,
        label=body.label,
    )
    return IntegrationCreatedOut(
        **_integration_out(record).model_dump(),
        api_key=generated.plaintext,
    )


def list_integrations(store: ClinicStore, *, user_id: UUID) -> List[IntegrationOut]:
    clinic, _membership = clinic_service.require_membership(store, user_id)
    return [_integration_out(row) for row in store.list_website_integrations(clinic.id)]


def revoke_integration(store: ClinicStore, *, user_id: UUID, integration_id: UUID) -> IntegrationOut:
    clinic, _membership = clinic_service.require_membership(store, user_id)
    try:
        record = store.revoke_website_integration(clinic_id=clinic.id, integration_id=integration_id)
    except ValueError as exc:
        if str(exc) == "integration_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "integration_not_found", "message": "Integration not found"},
            ) from exc
        raise
    return _integration_out(record)


def list_activity(store: ClinicStore, *, user_id: UUID, limit: int = 50) -> List[IntegrationActivityOut]:
    clinic, _membership = clinic_service.require_membership(store, user_id)
    return [_activity_out(row) for row in store.list_integration_activity(clinic.id, limit=limit)]


def resolve_integration_from_key(
    store: ClinicStore, settings: Settings, plaintext_key: str
) -> WebsiteIntegrationRecord:
    pepper = settings.lala_integration_key_pepper.strip()
    if len(pepper) < 16:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "pepper_missing",
                "message": "Integration key pepper is not configured",
            },
        )
    key_hash = hash_integration_key(plaintext_key, pepper)
    record = store.find_website_integration_by_hash(key_hash)
    if record is None or record.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_integration_key", "message": "Invalid or revoked integration key"},
        )
    return record


def _consultation_out(
    consultation: ConsultationRecord,
    *,
    status_value: str,
    dedupe: str,
    possible_phone_duplicate: bool = False,
) -> WebsiteConsultationOut:
    return WebsiteConsultationOut(
        consultation_id=consultation.id,
        customer_id=consultation.customer_id,
        status=status_value,  # type: ignore[arg-type]
        dedupe=DedupeOut(
            customer=dedupe,  # type: ignore[arg-type]
            possible_phone_duplicate=possible_phone_duplicate,
        ),
    )


def ingest_website_consultation(
    store: ClinicStore,
    *,
    integration: WebsiteIntegrationRecord,
    body: WebsiteConsultationIn,
    idempotency_key: str,
) -> Tuple[WebsiteConsultationOut, int]:
    clinic_id = integration.clinic_id
    existing = store.get_consultation_by_idempotency(
        clinic_id=clinic_id, idempotency_key=idempotency_key
    )
    if existing is not None:
        store.add_integration_activity(
            clinic_id=clinic_id,
            integration_id=integration.id,
            status="duplicate",
            reason="idempotency_replay",
            idempotency_key=idempotency_key,
        )
        customers = getattr(store, "customers", {})
        prior = customers.get(existing.customer_id) if isinstance(customers, dict) else None
        flagged = bool(getattr(prior, "possible_phone_duplicate", False))
        return (
            _consultation_out(
                existing,
                status_value="duplicate",
                dedupe="existing",
                possible_phone_duplicate=flagged,
            ),
            200,
        )

    email_normalized = str(body.email).strip().lower()
    phone_e164 = normalize_phone_e164(body.phone)
    customer, dedupe = store.upsert_customer_by_email(
        clinic_id=clinic_id,
        email_normalized=email_normalized,
        full_name=body.full_name,
        phone_e164=phone_e164,
    )
    consultation = store.create_consultation(
        clinic_id=clinic_id,
        customer_id=customer.id,
        category=body.category,
        service_external_id=body.service.external_id,
        service_name=body.service.name,
        external_enquiry_id=str(body.external_enquiry_id),
        consent_ai_call=body.consent.ai_call_consent,
        consent_text=body.consent.consent_text,
        consent_version=body.consent.consent_version,
        consented_at=body.consent.consented_at,
        source_website=body.source.website,
        source_submitted_at=body.source.submitted_at,
        idempotency_key=idempotency_key,
    )
    store.add_integration_activity(
        clinic_id=clinic_id,
        integration_id=integration.id,
        status="accepted",
        reason=None,
        idempotency_key=idempotency_key,
    )
    store.add_activity_event(
        clinic_id=clinic_id,
        actor_type="integration",
        action="consultation.accepted",
        entity_type="consultation",
        entity_id=consultation.id,
        payload={
            "customer_id": str(customer.id),
            "dedupe": dedupe,
            "source": body.source.website,
        },
    )
    return (
        _consultation_out(
            consultation,
            status_value="accepted",
            dedupe=dedupe,
            possible_phone_duplicate=customer.possible_phone_duplicate,
        ),
        201,
    )


def record_rejected_activity(
    store: ClinicStore,
    *,
    clinic_id: Optional[UUID],
    integration_id: Optional[UUID],
    reason: str,
    idempotency_key: Optional[str],
) -> None:
    if clinic_id is None:
        return
    store.add_integration_activity(
        clinic_id=clinic_id,
        integration_id=integration_id,
        status="rejected",
        reason=reason,
        idempotency_key=idempotency_key,
    )
