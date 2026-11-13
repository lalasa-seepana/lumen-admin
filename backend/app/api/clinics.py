from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SettingsDep, StoreDep
from app.models.clinics import ClinicCreate, ClinicOut, MeOut
from app.services import clinics as clinic_service

router = APIRouter(prefix="/v1/clinics", tags=["clinics"])


@router.post("", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def create_clinic(body: ClinicCreate, user: CurrentUser, store: StoreDep, settings: SettingsDep) -> MeOut:
    clinic, membership = clinic_service.create_clinic(store, settings, user_id=user.id, body=body)
    return MeOut(user_id=user.id, email=user.email, clinic=clinic, membership=membership)


@router.get("/current", response_model=ClinicOut)
def get_current_clinic(user: CurrentUser, store: StoreDep) -> ClinicOut:
    clinic, _membership = clinic_service.require_membership(store, user.id)
    return clinic


@router.get("/{clinic_id}", response_model=ClinicOut)
def get_clinic_by_id(clinic_id: UUID, user: CurrentUser, store: StoreDep) -> ClinicOut:
    return clinic_service.assert_clinic_access(store, user.id, clinic_id)
