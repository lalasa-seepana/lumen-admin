from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, StoreDep
from app.models.onboarding import OnboardingClinicUpdate, OnboardingStateOut
from app.services import onboarding as onboarding_service

router = APIRouter(prefix="/v1/onboarding", tags=["onboarding"])


@router.get("", response_model=OnboardingStateOut)
def get_onboarding(user: CurrentUser, store: StoreDep) -> OnboardingStateOut:
    return onboarding_service.get_onboarding_state(store, user_id=user.id)


@router.patch("/clinic", response_model=OnboardingStateOut)
def patch_onboarding_clinic(
    body: OnboardingClinicUpdate, user: CurrentUser, store: StoreDep
) -> OnboardingStateOut:
    return onboarding_service.update_clinic_profile(store, user_id=user.id, body=body)


@router.post("/steps/{step_key}/skip", response_model=OnboardingStateOut)
def skip_step(step_key: str, user: CurrentUser, store: StoreDep) -> OnboardingStateOut:
    return onboarding_service.skip_onboarding_step(store, user_id=user.id, step_key=step_key)