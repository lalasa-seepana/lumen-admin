from __future__ import annotations

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import ValidationError

from app.api.deps import CurrentUser, SettingsDep, StoreDep, get_bearer_token
from app.models.integrations import (
    IntegrationActivityOut,
    IntegrationCreate,
    IntegrationCreatedOut,
    IntegrationOut,
    WebsiteConsultationIn,
    WebsiteConsultationOut,
)
from app.services import integrations as integration_service
from app.services.clinic_store import WebsiteIntegrationRecord

router = APIRouter(tags=["integrations"])
owner_router = APIRouter(prefix="/v1/integrations", tags=["integrations"])
website_router = APIRouter(prefix="/v1/integrations/website", tags=["integrations"])


def get_active_integration(
    token: Annotated[str, Depends(get_bearer_token)],
    store: StoreDep,
    settings: SettingsDep,
) -> WebsiteIntegrationRecord:
    return integration_service.resolve_integration_from_key(store, settings, token)


IntegrationAuth = Annotated[WebsiteIntegrationRecord, Depends(get_active_integration)]


@owner_router.post("", response_model=IntegrationCreatedOut, status_code=status.HTTP_201_CREATED)
def create_integration(
    body: IntegrationCreate,
    user: CurrentUser,
    store: StoreDep,
    settings: SettingsDep,
) -> IntegrationCreatedOut:
    return integration_service.create_integration(store, settings, user_id=user.id, body=body)


@owner_router.get("", response_model=List[IntegrationOut])
def list_integrations(user: CurrentUser, store: StoreDep) -> List[IntegrationOut]:
    return integration_service.list_integrations(store, user_id=user.id)


@owner_router.post("/{integration_id}/revoke", response_model=IntegrationOut)
def revoke_integration(
    integration_id: UUID, user: CurrentUser, store: StoreDep
) -> IntegrationOut:
    return integration_service.revoke_integration(
        store, user_id=user.id, integration_id=integration_id
    )


@owner_router.get("/activity", response_model=List[IntegrationActivityOut])
def list_integration_activity(user: CurrentUser, store: StoreDep) -> List[IntegrationActivityOut]:
    return integration_service.list_activity(store, user_id=user.id)


@website_router.post("/consultations", response_model=WebsiteConsultationOut)
async def ingest_consultation(
    request: Request,
    response: Response,
    integration: IntegrationAuth,
    store: StoreDep,
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> WebsiteConsultationOut:
    raw = await request.json()
    if not isinstance(raw, dict):
        integration_service.record_rejected_activity(
            store,
            clinic_id=integration.clinic_id,
            integration_id=integration.id,
            reason="invalid_json_object",
            idempotency_key=idempotency_key,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_body", "message": "Request body must be a JSON object"},
        )

    # Reject client-supplied clinic/tenant spoofing fields explicitly.
    for forbidden in ("clinic_id", "tenant_id", "clinicId", "tenantId"):
        if forbidden in raw:
            integration_service.record_rejected_activity(
                store,
                clinic_id=integration.clinic_id,
                integration_id=integration.id,
                reason="clinic_spoof_rejected",
                idempotency_key=idempotency_key,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "clinic_spoof_rejected",
                    "message": "Clinic is resolved from the integration key only",
                },
            )

    try:
        body = WebsiteConsultationIn.model_validate(raw)
    except ValidationError as exc:
        integration_service.record_rejected_activity(
            store,
            clinic_id=integration.clinic_id,
            integration_id=integration.id,
            reason="schema_validation",
            idempotency_key=idempotency_key,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": "Request failed strict schema validation",
                "errors": exc.errors(),
            },
        ) from exc

    key = (idempotency_key or "").strip()
    if not key:
        integration_service.record_rejected_activity(
            store,
            clinic_id=integration.clinic_id,
            integration_id=integration.id,
            reason="missing_idempotency_key",
            idempotency_key=None,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "missing_idempotency_key",
                "message": "Idempotency-Key header is required",
            },
        )

    result, status_code = integration_service.ingest_website_consultation(
        store,
        integration=integration,
        body=body,
        idempotency_key=key,
    )
    response.status_code = status_code
    return result


@website_router.get("/ping")
def ping_integration(integration: IntegrationAuth, store: StoreDep) -> dict:
    """Validate an integration key without writing enquiries or patients."""
    clinic = store.get_clinic(integration.clinic_id)
    return {
        "status": "ok",
        "clinic_id": str(integration.clinic_id),
        "clinic_name": clinic.name if clinic else None,
        "integration_id": str(integration.id),
        "key_prefix": integration.key_prefix,
    }


router.include_router(owner_router)
router.include_router(website_router)
