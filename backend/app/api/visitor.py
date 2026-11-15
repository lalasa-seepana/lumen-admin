from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SettingsDep, StoreDep
from app.models.visitor import VisitorClinicOut, VisitorSessionCreate, VisitorSessionOut
from app.services import visitor_sessions as visitor_service

router = APIRouter(prefix="/v1/visitor", tags=["visitor"])


@router.get("/clinic/{slug}", response_model=VisitorClinicOut)
def get_visitor_clinic(slug: str, store: StoreDep) -> VisitorClinicOut:
    record = store.get_clinic_by_slug(slug)
    if record is None:
        # Also allow lookup by UUID string for dashboard test links.
        try:
            from uuid import UUID

            record = store.get_clinic(UUID(slug))
        except Exception:
            record = None
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "clinic_not_found", "message": "Clinic not found"},
        )
    return VisitorClinicOut(
        id=record.id,
        name=record.name,
        public_slug=record.public_slug,
        timezone=record.timezone,
    )


@router.post("/sessions", response_model=VisitorSessionOut, status_code=status.HTTP_201_CREATED)
def create_visitor_session(
    body: VisitorSessionCreate, store: StoreDep, settings: SettingsDep
) -> VisitorSessionOut:
    return visitor_service.create_public_session(store, settings, body=body)