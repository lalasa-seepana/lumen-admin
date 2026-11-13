from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional, Protocol, Tuple
from uuid import UUID, uuid4


@dataclass
class ClinicRecord:
    id: UUID
    name: str
    timezone: str
    created_at: datetime


@dataclass
class MembershipRecord:
    clinic_id: UUID
    user_id: UUID
    role: str
    created_at: datetime


class ClinicStore(Protocol):
    def get_membership(self, user_id: UUID) -> Optional[MembershipRecord]: ...

    def get_clinic(self, clinic_id: UUID) -> Optional[ClinicRecord]: ...

    def create_clinic_for_owner(
        self, *, user_id: UUID, name: str, timezone_name: str
    ) -> Tuple[ClinicRecord, MembershipRecord]: ...

    def list_memberships_for_clinic(self, clinic_id: UUID) -> List[MembershipRecord]: ...


@dataclass
class InMemoryClinicStore:
    """Process-local store for Epic 1 tests and local demos without a live Lala DB."""

    clinics: Dict[UUID, ClinicRecord] = field(default_factory=dict)
    memberships_by_user: Dict[UUID, MembershipRecord] = field(default_factory=dict)
    memberships_by_clinic: Dict[UUID, List[MembershipRecord]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def get_membership(self, user_id: UUID) -> Optional[MembershipRecord]:
        return self.memberships_by_user.get(user_id)

    def get_clinic(self, clinic_id: UUID) -> Optional[ClinicRecord]:
        return self.clinics.get(clinic_id)

    def list_memberships_for_clinic(self, clinic_id: UUID) -> List[MembershipRecord]:
        return list(self.memberships_by_clinic.get(clinic_id, []))

    def create_clinic_for_owner(
        self, *, user_id: UUID, name: str, timezone_name: str
    ) -> Tuple[ClinicRecord, MembershipRecord]:
        with self._lock:
            existing = self.memberships_by_user.get(user_id)
            if existing is not None:
                raise ValueError("owner_already_has_clinic")
            now = datetime.now(timezone.utc)
            clinic = ClinicRecord(id=uuid4(), name=name, timezone=timezone_name, created_at=now)
            membership = MembershipRecord(
                clinic_id=clinic.id, user_id=user_id, role="owner", created_at=now
            )
            self.clinics[clinic.id] = clinic
            self.memberships_by_user[user_id] = membership
            self.memberships_by_clinic.setdefault(clinic.id, []).append(membership)
            return clinic, membership


_store: Optional[InMemoryClinicStore] = None


def get_clinic_store() -> InMemoryClinicStore:
    global _store
    if _store is None:
        _store = InMemoryClinicStore()
    return _store


def reset_clinic_store() -> InMemoryClinicStore:
    global _store
    _store = InMemoryClinicStore()
    return _store
