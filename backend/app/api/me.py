from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, StoreDep
from app.models.clinics import MeOut
from app.services import clinics as clinic_service

router = APIRouter(tags=["auth"])


@router.get("/v1/me", response_model=MeOut)
def read_me(user: CurrentUser, store: StoreDep) -> MeOut:
    clinic, membership = clinic_service.get_current_clinic(store, user.id)
    return MeOut(user_id=user.id, email=user.email, clinic=clinic, membership=membership)
