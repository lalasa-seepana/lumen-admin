from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Protocol, Tuple
from uuid import UUID, uuid4

from app.services.booking_records import BookingMixin


@dataclass
class ClinicRecord:
    id: UUID
    name: str
    timezone: str
    created_at: datetime
    public_slug: str = ""
    website_url: Optional[str] = None
    website_last_error: Optional[str] = None
    scheduling_mode: str = "unset"
    google_refresh_token_enc: Optional[str] = None
    google_calendar_id: Optional[str] = None
    google_last_sync_at: Optional[datetime] = None
    google_last_error: Optional[str] = None
    google_status: str = "disconnected"


def _slugify_clinic_name(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:48] or "clinic"
    return f"{base}-{secrets.token_hex(3)}"


@dataclass
class MembershipRecord:
    clinic_id: UUID
    user_id: UUID
    role: str
    created_at: datetime


@dataclass
class WebsiteIntegrationRecord:
    id: UUID
    clinic_id: UUID
    key_hash: str
    key_prefix: str
    label: str
    revoked_at: Optional[datetime]
    created_at: datetime


@dataclass
class CustomerRecord:
    id: UUID
    clinic_id: UUID
    email_normalized: str
    full_name: str
    phone_e164: Optional[str]
    possible_phone_duplicate: bool
    created_at: datetime


@dataclass
class ConsultationRecord:
    id: UUID
    clinic_id: UUID
    customer_id: UUID
    category: str
    service_external_id: Optional[str]
    service_name: Optional[str]
    external_enquiry_id: str
    consent_ai_call: bool
    consent_text: str
    consent_version: str
    consented_at: datetime
    source_website: str
    source_submitted_at: datetime
    idempotency_key: str
    created_at: datetime


@dataclass
class IntegrationActivityRecord:
    id: UUID
    clinic_id: UUID
    integration_id: Optional[UUID]
    status: str
    reason: Optional[str]
    idempotency_key: Optional[str]
    created_at: datetime


@dataclass
class ActivityEventRecord:
    id: UUID
    clinic_id: UUID
    actor_type: str
    action: str
    entity_type: str
    entity_id: Optional[UUID]
    payload: dict
    created_at: datetime


@dataclass
class OAuthStateRecord:
    state: str
    clinic_id: UUID
    user_id: UUID
    provider: str
    expires_at: datetime
    created_at: datetime


@dataclass
class CalendarProviderConnectionRecord:
    clinic_id: UUID
    provider: str
    api_key_enc: Optional[str]
    status: str
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    config: dict
    webhook_secret: Optional[str]
    created_at: datetime
    updated_at: datetime


class ClinicStore(Protocol):
    def get_membership(self, user_id: UUID) -> Optional[MembershipRecord]: ...

    def get_clinic(self, clinic_id: UUID) -> Optional[ClinicRecord]: ...

    def create_clinic_for_owner(
        self, *, user_id: UUID, name: str, timezone_name: str
    ) -> Tuple[ClinicRecord, MembershipRecord]: ...

    def list_memberships_for_clinic(self, clinic_id: UUID) -> List[MembershipRecord]: ...

    def create_website_integration(
        self, *, clinic_id: UUID, key_hash: str, key_prefix: str, label: str
    ) -> WebsiteIntegrationRecord: ...

    def list_website_integrations(self, clinic_id: UUID) -> List[WebsiteIntegrationRecord]: ...

    def get_website_integration(self, integration_id: UUID) -> Optional[WebsiteIntegrationRecord]: ...

    def find_website_integration_by_hash(self, key_hash: str) -> Optional[WebsiteIntegrationRecord]: ...

    def revoke_website_integration(
        self, *, clinic_id: UUID, integration_id: UUID
    ) -> WebsiteIntegrationRecord: ...

    def upsert_customer_by_email(
        self,
        *,
        clinic_id: UUID,
        email_normalized: str,
        full_name: str,
        phone_e164: Optional[str],
    ) -> Tuple[CustomerRecord, str]: ...

    def get_consultation_by_idempotency(
        self, *, clinic_id: UUID, idempotency_key: str
    ) -> Optional[ConsultationRecord]: ...

    def create_consultation(self, **kwargs) -> ConsultationRecord: ...

    def add_integration_activity(
        self,
        *,
        clinic_id: UUID,
        integration_id: Optional[UUID],
        status: str,
        reason: Optional[str],
        idempotency_key: Optional[str],
    ) -> IntegrationActivityRecord: ...

    def list_integration_activity(
        self, clinic_id: UUID, *, limit: int = 50
    ) -> List[IntegrationActivityRecord]: ...

    def list_consultations(self, clinic_id: UUID, *, limit: int = 100) -> List[ConsultationRecord]: ...

    def list_customers(self, clinic_id: UUID, *, limit: int = 100) -> List[CustomerRecord]: ...

    def get_customer(self, clinic_id: UUID, customer_id: UUID) -> Optional[CustomerRecord]: ...

    def list_consultations_for_customer(
        self, clinic_id: UUID, customer_id: UUID
    ) -> List[ConsultationRecord]: ...

    def add_activity_event(
        self,
        *,
        clinic_id: UUID,
        actor_type: str,
        action: str,
        entity_type: str,
        entity_id: Optional[UUID],
        payload: Optional[dict] = None,
    ) -> ActivityEventRecord: ...

    def list_activity_events(self, clinic_id: UUID, *, limit: int = 100) -> List[ActivityEventRecord]: ...

    def get_clinic_by_slug(self, public_slug: str) -> Optional[ClinicRecord]: ...

    def update_clinic(self, clinic_id: UUID, **fields: Any) -> ClinicRecord: ...


@dataclass
class InMemoryClinicStore(BookingMixin):
    """Process-local store for Epic 1–7 tests and local demos without a live Clinic Dial DB."""

    clinics: Dict[UUID, ClinicRecord] = field(default_factory=dict)
    memberships_by_user: Dict[UUID, MembershipRecord] = field(default_factory=dict)
    memberships_by_clinic: Dict[UUID, List[MembershipRecord]] = field(default_factory=dict)
    integrations: Dict[UUID, WebsiteIntegrationRecord] = field(default_factory=dict)
    integrations_by_hash: Dict[str, UUID] = field(default_factory=dict)
    customers: Dict[UUID, CustomerRecord] = field(default_factory=dict)
    customers_by_clinic_email: Dict[Tuple[UUID, str], UUID] = field(default_factory=dict)
    consultations: Dict[UUID, ConsultationRecord] = field(default_factory=dict)
    consultations_by_idempotency: Dict[Tuple[UUID, str], UUID] = field(default_factory=dict)
    activity: List[IntegrationActivityRecord] = field(default_factory=list)
    activity_events: List[ActivityEventRecord] = field(default_factory=list)
    clinics_by_slug: Dict[str, UUID] = field(default_factory=dict)
    oauth_states: Dict[str, OAuthStateRecord] = field(default_factory=dict)
    calendar_connections: Dict[Tuple[UUID, str], CalendarProviderConnectionRecord] = field(
        default_factory=dict
    )
    _lock: Lock = field(default_factory=Lock)

    def get_membership(self, user_id: UUID) -> Optional[MembershipRecord]:
        return self.memberships_by_user.get(user_id)

    def get_clinic(self, clinic_id: UUID) -> Optional[ClinicRecord]:
        return self.clinics.get(clinic_id)

    def get_clinic_by_slug(self, public_slug: str) -> Optional[ClinicRecord]:
        clinic_id = self.clinics_by_slug.get(public_slug.strip().lower())
        if clinic_id is None:
            return None
        return self.clinics.get(clinic_id)

    def update_clinic(self, clinic_id: UUID, **fields: Any) -> ClinicRecord:
        with self._lock:
            existing = self.clinics.get(clinic_id)
            if existing is None:
                raise ValueError("clinic_not_found")
            if "public_slug" in fields and fields["public_slug"]:
                new_slug = str(fields["public_slug"]).strip().lower()
                old_slug = existing.public_slug
                if new_slug != old_slug:
                    if new_slug in self.clinics_by_slug and self.clinics_by_slug[new_slug] != clinic_id:
                        raise ValueError("slug_taken")
                    if old_slug:
                        self.clinics_by_slug.pop(old_slug, None)
                    self.clinics_by_slug[new_slug] = clinic_id
            patch = {k: v for k, v in fields.items() if hasattr(existing, k)}
            updated = replace(existing, **patch)
            self.clinics[clinic_id] = updated
            return updated

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
            slug = _slugify_clinic_name(name)
            while slug in self.clinics_by_slug:
                slug = _slugify_clinic_name(name)
            clinic = ClinicRecord(
                id=uuid4(),
                name=name,
                timezone=timezone_name,
                created_at=now,
                public_slug=slug,
            )
            membership = MembershipRecord(
                clinic_id=clinic.id, user_id=user_id, role="owner", created_at=now
            )
            self.clinics[clinic.id] = clinic
            self.clinics_by_slug[slug] = clinic.id
            self.init_onboarding_steps(clinic.id, completed=["clinic_profile"])
            self.memberships_by_user[user_id] = membership
            self.memberships_by_clinic.setdefault(clinic.id, []).append(membership)
            return clinic, membership

    def create_website_integration(
        self, *, clinic_id: UUID, key_hash: str, key_prefix: str, label: str
    ) -> WebsiteIntegrationRecord:
        with self._lock:
            if key_hash in self.integrations_by_hash:
                raise ValueError("key_hash_collision")
            now = datetime.now(timezone.utc)
            record = WebsiteIntegrationRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                key_hash=key_hash,
                key_prefix=key_prefix,
                label=label,
                revoked_at=None,
                created_at=now,
            )
            self.integrations[record.id] = record
            self.integrations_by_hash[key_hash] = record.id
            return record

    def list_website_integrations(self, clinic_id: UUID) -> List[WebsiteIntegrationRecord]:
        rows = [row for row in self.integrations.values() if row.clinic_id == clinic_id]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    def get_website_integration(self, integration_id: UUID) -> Optional[WebsiteIntegrationRecord]:
        return self.integrations.get(integration_id)

    def find_website_integration_by_hash(self, key_hash: str) -> Optional[WebsiteIntegrationRecord]:
        integration_id = self.integrations_by_hash.get(key_hash)
        if integration_id is None:
            return None
        return self.integrations.get(integration_id)

    def revoke_website_integration(
        self, *, clinic_id: UUID, integration_id: UUID
    ) -> WebsiteIntegrationRecord:
        with self._lock:
            record = self.integrations.get(integration_id)
            if record is None or record.clinic_id != clinic_id:
                raise ValueError("integration_not_found")
            if record.revoked_at is not None:
                return record
            revoked = WebsiteIntegrationRecord(
                id=record.id,
                clinic_id=record.clinic_id,
                key_hash=record.key_hash,
                key_prefix=record.key_prefix,
                label=record.label,
                revoked_at=datetime.now(timezone.utc),
                created_at=record.created_at,
            )
            self.integrations[integration_id] = revoked
            return revoked

    def _phone_owned_by_other(
        self, *, clinic_id: UUID, phone_e164: Optional[str], exclude_customer_id: Optional[UUID]
    ) -> bool:
        if not phone_e164:
            return False
        for customer in self.customers.values():
            if customer.clinic_id != clinic_id:
                continue
            if exclude_customer_id is not None and customer.id == exclude_customer_id:
                continue
            if customer.phone_e164 and customer.phone_e164 == phone_e164:
                return True
        return False

    def upsert_customer_by_email(
        self,
        *,
        clinic_id: UUID,
        email_normalized: str,
        full_name: str,
        phone_e164: Optional[str],
    ) -> Tuple[CustomerRecord, str]:
        with self._lock:
            key = (clinic_id, email_normalized)
            existing_id = self.customers_by_clinic_email.get(key)
            if existing_id is not None:
                existing = self.customers[existing_id]
                # Fill missing phone only — never overwrite an existing value.
                phone = existing.phone_e164 if existing.phone_e164 else phone_e164
                flagged = existing.possible_phone_duplicate or self._phone_owned_by_other(
                    clinic_id=clinic_id, phone_e164=phone, exclude_customer_id=existing.id
                )
                updated = CustomerRecord(
                    id=existing.id,
                    clinic_id=existing.clinic_id,
                    email_normalized=existing.email_normalized,
                    full_name=existing.full_name,
                    phone_e164=phone,
                    possible_phone_duplicate=flagged,
                    created_at=existing.created_at,
                )
                self.customers[existing.id] = updated
                return updated, "existing"
            flagged = self._phone_owned_by_other(
                clinic_id=clinic_id, phone_e164=phone_e164, exclude_customer_id=None
            )
            now = datetime.now(timezone.utc)
            customer = CustomerRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                email_normalized=email_normalized,
                full_name=full_name,
                phone_e164=phone_e164,
                possible_phone_duplicate=flagged,
                created_at=now,
            )
            self.customers[customer.id] = customer
            self.customers_by_clinic_email[key] = customer.id
            return customer, "created"

    def get_consultation_by_idempotency(
        self, *, clinic_id: UUID, idempotency_key: str
    ) -> Optional[ConsultationRecord]:
        consultation_id = self.consultations_by_idempotency.get((clinic_id, idempotency_key))
        if consultation_id is None:
            return None
        return self.consultations.get(consultation_id)

    def create_consultation(
        self,
        *,
        clinic_id: UUID,
        customer_id: UUID,
        category: str,
        service_external_id: Optional[str],
        service_name: Optional[str],
        external_enquiry_id: str,
        consent_ai_call: bool,
        consent_text: str,
        consent_version: str,
        consented_at: datetime,
        source_website: str,
        source_submitted_at: datetime,
        idempotency_key: str,
    ) -> ConsultationRecord:
        with self._lock:
            key = (clinic_id, idempotency_key)
            if key in self.consultations_by_idempotency:
                raise ValueError("idempotency_conflict")
            now = datetime.now(timezone.utc)
            record = ConsultationRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                customer_id=customer_id,
                category=category,
                service_external_id=service_external_id,
                service_name=service_name,
                external_enquiry_id=external_enquiry_id,
                consent_ai_call=consent_ai_call,
                consent_text=consent_text,
                consent_version=consent_version,
                consented_at=consented_at,
                source_website=source_website,
                source_submitted_at=source_submitted_at,
                idempotency_key=idempotency_key,
                created_at=now,
            )
            self.consultations[record.id] = record
            self.consultations_by_idempotency[key] = record.id
            return record

    def add_integration_activity(
        self,
        *,
        clinic_id: UUID,
        integration_id: Optional[UUID],
        status: str,
        reason: Optional[str],
        idempotency_key: Optional[str],
    ) -> IntegrationActivityRecord:
        with self._lock:
            record = IntegrationActivityRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                integration_id=integration_id,
                status=status,
                reason=reason,
                idempotency_key=idempotency_key,
                created_at=datetime.now(timezone.utc),
            )
            self.activity.append(record)
            return record

    def list_integration_activity(
        self, clinic_id: UUID, *, limit: int = 50
    ) -> List[IntegrationActivityRecord]:
        rows = [row for row in self.activity if row.clinic_id == clinic_id]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[:limit]

    def list_consultations(self, clinic_id: UUID, *, limit: int = 100) -> List[ConsultationRecord]:
        rows = [row for row in self.consultations.values() if row.clinic_id == clinic_id]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[:limit]

    def list_customers(self, clinic_id: UUID, *, limit: int = 100) -> List[CustomerRecord]:
        rows = [row for row in self.customers.values() if row.clinic_id == clinic_id]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[:limit]

    def get_customer(self, clinic_id: UUID, customer_id: UUID) -> Optional[CustomerRecord]:
        row = self.customers.get(customer_id)
        if row is None or row.clinic_id != clinic_id:
            return None
        return row

    def list_consultations_for_customer(
        self, clinic_id: UUID, customer_id: UUID
    ) -> List[ConsultationRecord]:
        rows = [
            row
            for row in self.consultations.values()
            if row.clinic_id == clinic_id and row.customer_id == customer_id
        ]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows

    def add_activity_event(
        self,
        *,
        clinic_id: UUID,
        actor_type: str,
        action: str,
        entity_type: str,
        entity_id: Optional[UUID],
        payload: Optional[dict] = None,
    ) -> ActivityEventRecord:
        with self._lock:
            record = ActivityEventRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                actor_type=actor_type,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload or {},
                created_at=datetime.now(timezone.utc),
            )
            self.activity_events.append(record)
            return record

    def list_activity_events(self, clinic_id: UUID, *, limit: int = 100) -> List[ActivityEventRecord]:
        rows = [row for row in self.activity_events if row.clinic_id == clinic_id]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[:limit]

    def save_oauth_state(
        self,
        *,
        state: str,
        clinic_id: UUID,
        user_id: UUID,
        provider: str,
        expires_at: datetime,
    ) -> OAuthStateRecord:
        with self._lock:
            now = datetime.now(timezone.utc)
            record = OAuthStateRecord(
                state=state,
                clinic_id=clinic_id,
                user_id=user_id,
                provider=provider,
                expires_at=expires_at,
                created_at=now,
            )
            self.oauth_states[state] = record
            return record

    def take_oauth_state(self, state: str) -> Optional[OAuthStateRecord]:
        with self._lock:
            return self.oauth_states.pop(state, None)

    def get_calendar_provider_connection(
        self, clinic_id: UUID, provider: str
    ) -> Optional[CalendarProviderConnectionRecord]:
        return self.calendar_connections.get((clinic_id, provider))

    def upsert_calendar_provider_connection(
        self,
        *,
        clinic_id: UUID,
        provider: str,
        api_key_enc: Optional[str] = None,
        status: str = "disconnected",
        last_sync_at: Optional[datetime] = None,
        last_error: Optional[str] = None,
        config: Optional[dict] = None,
        webhook_secret: Optional[str] = None,
    ) -> CalendarProviderConnectionRecord:
        with self._lock:
            now = datetime.now(timezone.utc)
            key = (clinic_id, provider)
            existing = self.calendar_connections.get(key)
            record = CalendarProviderConnectionRecord(
                clinic_id=clinic_id,
                provider=provider,
                api_key_enc=api_key_enc if api_key_enc is not None else (existing.api_key_enc if existing else None),
                status=status,
                last_sync_at=last_sync_at if last_sync_at is not None else (existing.last_sync_at if existing else None),
                last_error=last_error,
                config=config if config is not None else (existing.config if existing else {}),
                webhook_secret=webhook_secret
                if webhook_secret is not None
                else (existing.webhook_secret if existing else None),
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
            self.calendar_connections[key] = record
            return record


_store: Optional[ClinicStore] = None


def get_clinic_store() -> ClinicStore:
    global _store
    if _store is None:
        from app.core.config import get_settings

        settings = get_settings()
        if settings.database_configured:
            from app.services.postgres_store import PostgresClinicStore

            _store = PostgresClinicStore(settings.database_url)
        else:
            _store = InMemoryClinicStore()
    return _store


def reset_clinic_store() -> InMemoryClinicStore:
    """Always in-memory — used by tests."""
    global _store
    _store = InMemoryClinicStore()
    return _store
