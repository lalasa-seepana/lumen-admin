from __future__ import annotations

from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import Settings
from app.models.clinics import ClinicCreate, ClinicOut, MembershipOut
from app.services.clinic_store import ClinicStore, MembershipRecord


def _clinic_out(clinic) -> ClinicOut:
    return ClinicOut(
        id=clinic.id,
        name=clinic.name,
        timezone=clinic.timezone,
        created_at=clinic.created_at,
    )


def _membership_out(membership: MembershipRecord) -> MembershipOut:
    return MembershipOut(
        clinic_id=membership.clinic_id,
        user_id=membership.user_id,
        role="owner",
    )


def get_current_clinic(
    store: ClinicStore, user_id: UUID
) -> Tuple[Optional[ClinicOut], Optional[MembershipOut]]:
    membership = store.get_membership(user_id)
    if membership is None:
        return None, None
    clinic = store.get_clinic(membership.clinic_id)
    if clinic is None:
        return None, None
    return _clinic_out(clinic), _membership_out(membership)


def require_membership(store: ClinicStore, user_id: UUID) -> Tuple[ClinicOut, MembershipOut]:
    clinic, membership = get_current_clinic(store, user_id)
    if clinic is None or membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "no_clinic_membership", "message": "Complete clinic onboarding first"},
        )
    return clinic, membership


def assert_clinic_access(store: ClinicStore, user_id: UUID, clinic_id: UUID) -> ClinicOut:
    clinic, membership = require_membership(store, user_id)
    if membership.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "clinic_forbidden", "message": "You do not have access to this clinic"},
        )
    return clinic


def create_clinic(
    store: ClinicStore, settings: Settings, *, user_id: UUID, body: ClinicCreate
) -> Tuple[ClinicOut, MembershipOut]:
    timezone_name = (body.timezone or settings.lala_default_timezone).strip() or settings.lala_default_timezone
    try:
        clinic, membership = store.create_clinic_for_owner(
            user_id=user_id, name=body.name, timezone_name=timezone_name
        )
    except ValueError as exc:
        if str(exc) == "owner_already_has_clinic":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "clinic_exists", "message": "You already own a clinic"},
            ) from exc
        raise
    return _clinic_out(clinic), _membership_out(membership)
