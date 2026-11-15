from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.models.onboarding import OnboardingClinicUpdate, OnboardingStateOut, OnboardingStepOut
from app.services import clinics as clinic_service
from app.services.booking_records import ONBOARDING_STEP_KEYS
from app.services.clinic_store import ClinicStore


def _step_out(row) -> OnboardingStepOut:
    return OnboardingStepOut(
        key=row.step_key,
        status=row.status,
        detail=row.detail,
        error=row.error,
        updated_at=row.updated_at,
    )


def get_onboarding_state(store: ClinicStore, *, user_id: UUID) -> OnboardingStateOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    record = store.get_clinic(clinic.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "clinic_not_found"})
    steps = store.list_onboarding_steps(clinic.id)
    if not steps:
        store.init_onboarding_steps(clinic.id, completed=["clinic_profile"])
        steps = store.list_onboarding_steps(clinic.id)
    return OnboardingStateOut(
        clinic_name=record.name,
        timezone=record.timezone,
        website_url=record.website_url,
        steps=[_step_out(row) for row in steps],
    )


def update_clinic_profile(
    store: ClinicStore, *, user_id: UUID, body: OnboardingClinicUpdate
) -> OnboardingStateOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    store.update_clinic(clinic.id, name=body.name.strip(), timezone=body.timezone.strip())
    store.upsert_onboarding_step(clinic_id=clinic.id, step_key="clinic_profile", status="completed")
    return get_onboarding_state(store, user_id=user_id)


def skip_onboarding_step(store: ClinicStore, *, user_id: UUID, step_key: str) -> OnboardingStateOut:
    if step_key not in ONBOARDING_STEP_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "step_not_found", "message": "Unknown onboarding step"},
        )
    clinic, _ = clinic_service.require_membership(store, user_id)
    store.upsert_onboarding_step(clinic_id=clinic.id, step_key=step_key, status="skipped")
    return get_onboarding_state(store, user_id=user_id)


def complete_step_if_hours_present(store: ClinicStore, clinic_id: UUID) -> None:
    if store.list_availability(clinic_id):
        store.upsert_onboarding_step(clinic_id=clinic_id, step_key="opening_hours", status="completed")