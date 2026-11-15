from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4


@dataclass
class ServiceRecord:
    id: UUID
    clinic_id: UUID
    name: str
    category: str
    duration_minutes: int
    price_paise: Optional[int]
    active: bool
    created_at: datetime
    source_url: Optional[str] = None
    imported_at: Optional[datetime] = None


@dataclass
class ServiceImportDraftRecord:
    id: UUID
    clinic_id: UUID
    name: Optional[str]
    description: Optional[str]
    duration_minutes: Optional[int]
    price_paise: Optional[int]
    currency: Optional[str]
    category: Optional[str]
    source_url: Optional[str]
    imported_at: datetime
    status: str


@dataclass
class WebsitePageRecord:
    id: UUID
    clinic_id: UUID
    url: str
    title: str
    fetched_at: datetime
    body_excerpt: str


@dataclass
class OnboardingStepRecord:
    clinic_id: UUID
    step_key: str
    status: str
    detail: Optional[str]
    error: Optional[str]
    updated_at: Optional[datetime]


@dataclass
class AvailabilityWindowRecord:
    id: UUID
    clinic_id: UUID
    weekday: int
    start_minute: int
    end_minute: int
    created_at: datetime


@dataclass
class AppointmentRecord:
    id: UUID
    clinic_id: UUID
    customer_id: UUID
    service_id: UUID
    starts_at_utc: datetime
    ends_at_utc: datetime
    status: str
    created_at: datetime
    idempotency_key: Optional[str] = None
    provider: str = "lala"
    sync_status: str = "local"
    external_event_id: Optional[str] = None
    voice_session_id: Optional[UUID] = None


@dataclass
class VoiceSessionRecord:
    id: UUID
    clinic_id: UUID
    language: str
    recording_consent: bool
    status: str
    created_at: datetime
    closed_at: Optional[datetime] = None
    visitor_token: Optional[str] = None
    actor_type: str = "owner"
    customer_id: Optional[UUID] = None
    customer_verified_at: Optional[datetime] = None
    pending_email: Optional[str] = None
    pending_phone: Optional[str] = None
    pending_full_name: Optional[str] = None
    verification_code_hash: Optional[str] = None
    verification_expires_at: Optional[datetime] = None
    verification_attempts: int = 0
    selected_service_id: Optional[UUID] = None
    selected_starts_at_utc: Optional[datetime] = None
    callback_contact: Optional[str] = None
    consent_version: Optional[str] = None
    consent_recorded_at: Optional[datetime] = None


@dataclass
class HandoverRecord:
    id: UUID
    clinic_id: UUID
    voice_session_id: Optional[UUID]
    reason: str
    summary: str
    status: str
    created_at: datetime
    conversation_id: Optional[UUID] = None
    callback_contact: Optional[str] = None


@dataclass
class ConversationRecord:
    id: UUID
    clinic_id: UUID
    voice_session_id: UUID
    language: str
    recording_consent: bool
    retention_until: datetime
    created_at: datetime
    deleted_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


@dataclass
class ConversationTurnRecord:
    id: UUID
    conversation_id: UUID
    clinic_id: UUID
    sequence: int
    role: str
    text: str
    has_audio_blob: bool
    audio_storage_key: Optional[str]
    created_at: datetime


@dataclass
class ToolAuditRecord:
    id: UUID
    clinic_id: UUID
    voice_session_id: Optional[UUID]
    tool_name: str
    accepted: bool
    reason: Optional[str]
    arguments: dict
    created_at: datetime


@dataclass
class BookingMixin:
    """In-memory booking + voice records mixed into InMemoryClinicStore."""

    services: Dict[UUID, ServiceRecord] = field(default_factory=dict)
    availability: List[AvailabilityWindowRecord] = field(default_factory=list)
    appointments: Dict[UUID, AppointmentRecord] = field(default_factory=dict)
    voice_sessions: Dict[UUID, VoiceSessionRecord] = field(default_factory=dict)
    handovers: Dict[UUID, HandoverRecord] = field(default_factory=dict)
    conversations: Dict[UUID, ConversationRecord] = field(default_factory=dict)
    conversation_turns: Dict[UUID, ConversationTurnRecord] = field(default_factory=dict)
    tool_audits: List[ToolAuditRecord] = field(default_factory=list)
    import_drafts: Dict[UUID, ServiceImportDraftRecord] = field(default_factory=dict)
    website_pages: Dict[UUID, WebsitePageRecord] = field(default_factory=dict)
    onboarding_steps: Dict[Tuple[UUID, str], OnboardingStepRecord] = field(default_factory=dict)
    _booking_lock: Lock = field(default_factory=Lock)

    def init_onboarding_steps(self, clinic_id: UUID, *, completed: Optional[List[str]] = None) -> None:
        now = datetime.now(timezone.utc)
        done = set(completed or [])
        for key in ONBOARDING_STEP_KEYS:
            status = "completed" if key in done else "incomplete"
            self.onboarding_steps[(clinic_id, key)] = OnboardingStepRecord(
                clinic_id=clinic_id,
                step_key=key,
                status=status,
                detail=None,
                error=None,
                updated_at=now if status == "completed" else None,
            )

    def list_onboarding_steps(self, clinic_id: UUID) -> List[OnboardingStepRecord]:
        rows = [row for (cid, _), row in self.onboarding_steps.items() if cid == clinic_id]
        return sorted(rows, key=lambda row: ONBOARDING_STEP_KEYS.index(row.step_key))

    def upsert_onboarding_step(
        self,
        *,
        clinic_id: UUID,
        step_key: str,
        status: str,
        detail: Optional[str] = None,
        error: Optional[str] = None,
    ) -> OnboardingStepRecord:
        now = datetime.now(timezone.utc)
        row = OnboardingStepRecord(
            clinic_id=clinic_id,
            step_key=step_key,
            status=status,
            detail=detail,
            error=error,
            updated_at=now,
        )
        self.onboarding_steps[(clinic_id, step_key)] = row
        return row

    def list_service_import_drafts(self, clinic_id: UUID) -> List[ServiceImportDraftRecord]:
        rows = [row for row in self.import_drafts.values() if row.clinic_id == clinic_id]
        return sorted(rows, key=lambda row: row.imported_at, reverse=True)

    def get_service_import_draft(
        self, clinic_id: UUID, draft_id: UUID
    ) -> Optional[ServiceImportDraftRecord]:
        row = self.import_drafts.get(draft_id)
        if row is None or row.clinic_id != clinic_id:
            return None
        return row

    def add_service_import_draft(
        self,
        *,
        clinic_id: UUID,
        name: Optional[str],
        description: Optional[str],
        duration_minutes: Optional[int],
        price_paise: Optional[int],
        currency: Optional[str],
        category: Optional[str],
        source_url: Optional[str],
    ) -> ServiceImportDraftRecord:
        with self._booking_lock:
            row = ServiceImportDraftRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                name=name,
                description=description,
                duration_minutes=duration_minutes,
                price_paise=price_paise,
                currency=currency,
                category=category,
                source_url=source_url,
                imported_at=datetime.now(timezone.utc),
                status="pending",
            )
            self.import_drafts[row.id] = row
            return row

    def update_service_import_draft(
        self, *, clinic_id: UUID, draft_id: UUID, **fields
    ) -> ServiceImportDraftRecord:
        with self._booking_lock:
            row = self.get_service_import_draft(clinic_id, draft_id)
            if row is None:
                raise ValueError("draft_not_found")
            updated = ServiceImportDraftRecord(
                id=row.id,
                clinic_id=row.clinic_id,
                name=fields.get("name", row.name),
                description=fields.get("description", row.description),
                duration_minutes=fields.get("duration_minutes", row.duration_minutes),
                price_paise=fields.get("price_paise", row.price_paise),
                currency=fields.get("currency", row.currency),
                category=fields.get("category", row.category),
                source_url=fields.get("source_url", row.source_url),
                imported_at=row.imported_at,
                status=fields.get("status", row.status),
            )
            self.import_drafts[draft_id] = updated
            return updated

    def list_website_pages(self, clinic_id: UUID) -> List[WebsitePageRecord]:
        rows = [row for row in self.website_pages.values() if row.clinic_id == clinic_id]
        return sorted(rows, key=lambda row: row.fetched_at, reverse=True)

    def add_website_page(
        self, *, clinic_id: UUID, url: str, title: str, body_excerpt: str
    ) -> WebsitePageRecord:
        with self._booking_lock:
            row = WebsitePageRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                url=url,
                title=title,
                fetched_at=datetime.now(timezone.utc),
                body_excerpt=body_excerpt[:8000],
            )
            self.website_pages[row.id] = row
            return row

    def create_service(
        self,
        *,
        clinic_id: UUID,
        name: str,
        category: str,
        duration_minutes: int,
        price_paise: Optional[int] = None,
        source_url: Optional[str] = None,
        imported_at: Optional[datetime] = None,
    ) -> ServiceRecord:
        with self._booking_lock:
            row = ServiceRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                name=name,
                category=category,
                duration_minutes=duration_minutes,
                price_paise=price_paise,
                active=True,
                created_at=datetime.now(timezone.utc),
                source_url=source_url,
                imported_at=imported_at,
            )
            self.services[row.id] = row
            return row

    def list_services(self, clinic_id: UUID, *, active_only: bool = True) -> List[ServiceRecord]:
        rows = [row for row in self.services.values() if row.clinic_id == clinic_id]
        if active_only:
            rows = [row for row in rows if row.active]
        return sorted(rows, key=lambda row: row.name)

    def get_service(self, clinic_id: UUID, service_id: UUID) -> Optional[ServiceRecord]:
        row = self.services.get(service_id)
        if row is None or row.clinic_id != clinic_id:
            return None
        return row

    def add_availability_window(
        self, *, clinic_id: UUID, weekday: int, start_minute: int, end_minute: int
    ) -> AvailabilityWindowRecord:
        with self._booking_lock:
            row = AvailabilityWindowRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                weekday=weekday,
                start_minute=start_minute,
                end_minute=end_minute,
                created_at=datetime.now(timezone.utc),
            )
            self.availability.append(row)
            return row

    def list_availability(self, clinic_id: UUID) -> List[AvailabilityWindowRecord]:
        return [row for row in self.availability if row.clinic_id == clinic_id]

    def get_appointment_by_idempotency(
        self, *, clinic_id: UUID, idempotency_key: str
    ) -> Optional[AppointmentRecord]:
        for row in self.appointments.values():
            if (
                row.clinic_id == clinic_id
                and row.idempotency_key
                and row.idempotency_key == idempotency_key
            ):
                return row
        return None

    def create_appointment(
        self,
        *,
        clinic_id: UUID,
        customer_id: UUID,
        service_id: UUID,
        starts_at_utc: datetime,
        ends_at_utc: datetime,
        idempotency_key: Optional[str] = None,
        provider: str = "lala",
        sync_status: str = "local",
        status: str = "booked",
        external_event_id: Optional[str] = None,
        voice_session_id: Optional[UUID] = None,
    ) -> AppointmentRecord:
        with self._booking_lock:
            if idempotency_key:
                for existing in self.appointments.values():
                    if (
                        existing.clinic_id == clinic_id
                        and existing.idempotency_key == idempotency_key
                    ):
                        return existing
            for existing in self.appointments.values():
                if existing.clinic_id != clinic_id or existing.status == "cancelled":
                    continue
                if starts_at_utc < existing.ends_at_utc and ends_at_utc > existing.starts_at_utc:
                    raise ValueError("appointment_conflict")
            row = AppointmentRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                customer_id=customer_id,
                service_id=service_id,
                starts_at_utc=starts_at_utc,
                ends_at_utc=ends_at_utc,
                status=status,
                created_at=datetime.now(timezone.utc),
                idempotency_key=idempotency_key,
                provider=provider,
                sync_status=sync_status,
                external_event_id=external_event_id,
                voice_session_id=voice_session_id,
            )
            self.appointments[row.id] = row
            return row

    def get_appointment(self, clinic_id: UUID, appointment_id: UUID) -> Optional[AppointmentRecord]:
        row = self.appointments.get(appointment_id)
        if row is None or row.clinic_id != clinic_id:
            return None
        return row

    def list_appointments(
        self, clinic_id: UUID, *, include_cancelled: bool = False
    ) -> List[AppointmentRecord]:
        rows = [row for row in self.appointments.values() if row.clinic_id == clinic_id]
        if not include_cancelled:
            rows = [row for row in rows if row.status != "cancelled"]
        return sorted(rows, key=lambda row: row.starts_at_utc)

    def list_appointments_for_voice_session(
        self, clinic_id: UUID, voice_session_id: UUID, *, include_cancelled: bool = False
    ) -> List[AppointmentRecord]:
        rows = [
            row
            for row in self.appointments.values()
            if row.clinic_id == clinic_id and row.voice_session_id == voice_session_id
        ]
        if not include_cancelled:
            rows = [row for row in rows if row.status != "cancelled"]
        return sorted(rows, key=lambda row: row.starts_at_utc)

    def update_appointment_sync(
        self,
        *,
        clinic_id: UUID,
        appointment_id: UUID,
        provider: str,
        sync_status: str,
        external_event_id: Optional[str],
    ) -> AppointmentRecord:
        with self._booking_lock:
            row = self.appointments.get(appointment_id)
            if row is None or row.clinic_id != clinic_id:
                raise ValueError("appointment_not_found")
            updated = AppointmentRecord(
                id=row.id,
                clinic_id=row.clinic_id,
                customer_id=row.customer_id,
                service_id=row.service_id,
                starts_at_utc=row.starts_at_utc,
                ends_at_utc=row.ends_at_utc,
                status=row.status,
                created_at=row.created_at,
                idempotency_key=row.idempotency_key,
                provider=provider,
                sync_status=sync_status,
                external_event_id=external_event_id,
                voice_session_id=row.voice_session_id,
            )
            self.appointments[appointment_id] = updated
            return updated

    def cancel_appointment(self, *, clinic_id: UUID, appointment_id: UUID) -> AppointmentRecord:
        with self._booking_lock:
            row = self.appointments.get(appointment_id)
            if row is None or row.clinic_id != clinic_id:
                raise ValueError("appointment_not_found")
            if row.status == "cancelled":
                return row
            updated = AppointmentRecord(
                id=row.id,
                clinic_id=row.clinic_id,
                customer_id=row.customer_id,
                service_id=row.service_id,
                starts_at_utc=row.starts_at_utc,
                ends_at_utc=row.ends_at_utc,
                status="cancelled",
                created_at=row.created_at,
                idempotency_key=row.idempotency_key,
                provider=row.provider,
                sync_status=row.sync_status,
                external_event_id=row.external_event_id,
                voice_session_id=row.voice_session_id,
            )
            self.appointments[appointment_id] = updated
            return updated

    def reschedule_appointment(
        self,
        *,
        clinic_id: UUID,
        appointment_id: UUID,
        starts_at_utc: datetime,
        ends_at_utc: datetime,
    ) -> AppointmentRecord:
        with self._booking_lock:
            row = self.appointments.get(appointment_id)
            if row is None or row.clinic_id != clinic_id:
                raise ValueError("appointment_not_found")
            if row.status == "cancelled":
                raise ValueError("appointment_cancelled")
            for existing in self.appointments.values():
                if existing.id == appointment_id:
                    continue
                if existing.clinic_id != clinic_id or existing.status == "cancelled":
                    continue
                if starts_at_utc < existing.ends_at_utc and ends_at_utc > existing.starts_at_utc:
                    raise ValueError("appointment_conflict")
            updated = AppointmentRecord(
                id=row.id,
                clinic_id=row.clinic_id,
                customer_id=row.customer_id,
                service_id=row.service_id,
                starts_at_utc=starts_at_utc,
                ends_at_utc=ends_at_utc,
                status="rescheduled",
                created_at=row.created_at,
                idempotency_key=row.idempotency_key,
                provider=row.provider,
                sync_status=row.sync_status,
                external_event_id=row.external_event_id,
                voice_session_id=row.voice_session_id,
            )
            self.appointments[appointment_id] = updated
            return updated

    def create_voice_session(
        self,
        *,
        clinic_id: UUID,
        language: str,
        recording_consent: bool,
        actor_type: str = "owner",
        consent_version: Optional[str] = None,
    ) -> VoiceSessionRecord:
        with self._booking_lock:
            if actor_type not in {"owner", "visitor"}:
                raise ValueError("invalid_actor_type")
            now = datetime.now(timezone.utc)
            row = VoiceSessionRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                language=language,
                recording_consent=recording_consent,
                status="open",
                created_at=now,
                visitor_token=secrets.token_urlsafe(32),
                actor_type=actor_type,
                consent_version=consent_version if recording_consent else None,
                consent_recorded_at=now if recording_consent else None,
            )
            self.voice_sessions[row.id] = row
            return row

    def get_voice_session(self, session_id: UUID) -> Optional[VoiceSessionRecord]:
        return self.voice_sessions.get(session_id)

    def update_voice_session(self, session_id: UUID, **fields) -> VoiceSessionRecord:
        with self._booking_lock:
            row = self.voice_sessions.get(session_id)
            if row is None:
                raise ValueError("session_not_found")
            data = {
                "id": row.id,
                "clinic_id": row.clinic_id,
                "language": row.language,
                "recording_consent": row.recording_consent,
                "status": row.status,
                "created_at": row.created_at,
                "closed_at": row.closed_at,
                "visitor_token": row.visitor_token,
                "actor_type": row.actor_type,
                "customer_id": row.customer_id,
                "customer_verified_at": row.customer_verified_at,
                "pending_email": row.pending_email,
                "pending_phone": row.pending_phone,
                "pending_full_name": row.pending_full_name,
                "verification_code_hash": row.verification_code_hash,
                "verification_expires_at": row.verification_expires_at,
                "verification_attempts": row.verification_attempts,
                "selected_service_id": row.selected_service_id,
                "selected_starts_at_utc": row.selected_starts_at_utc,
                "callback_contact": row.callback_contact,
                "consent_version": row.consent_version,
                "consent_recorded_at": row.consent_recorded_at,
            }
            data.update(fields)
            updated = VoiceSessionRecord(**data)
            self.voice_sessions[session_id] = updated
            return updated

    def create_handover(
        self,
        *,
        clinic_id: UUID,
        voice_session_id: Optional[UUID],
        reason: str,
        summary: str,
        conversation_id: Optional[UUID] = None,
        callback_contact: Optional[str] = None,
    ) -> HandoverRecord:
        with self._booking_lock:
            row = HandoverRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                voice_session_id=voice_session_id,
                reason=reason,
                summary=summary,
                status="open",
                created_at=datetime.now(timezone.utc),
                conversation_id=conversation_id,
                callback_contact=callback_contact,
            )
            self.handovers[row.id] = row
            return row

    def list_handovers(self, clinic_id: UUID) -> List[HandoverRecord]:
        rows = [row for row in self.handovers.values() if row.clinic_id == clinic_id]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    def get_handover(self, clinic_id: UUID, handover_id: UUID) -> Optional[HandoverRecord]:
        row = self.handovers.get(handover_id)
        if row is None or row.clinic_id != clinic_id:
            return None
        return row

    def set_handover_conversation(self, handover_id: UUID, conversation_id: UUID) -> None:
        with self._booking_lock:
            row = self.handovers.get(handover_id)
            if row is None:
                return
            self.handovers[handover_id] = HandoverRecord(
                id=row.id,
                clinic_id=row.clinic_id,
                voice_session_id=row.voice_session_id,
                reason=row.reason,
                summary=row.summary,
                status=row.status,
                created_at=row.created_at,
                conversation_id=conversation_id,
                callback_contact=row.callback_contact,
            )

    def update_handover_status(
        self, *, clinic_id: UUID, handover_id: UUID, status: str
    ) -> HandoverRecord:
        if status not in {"open", "acked", "closed"}:
            raise ValueError("invalid_handover_status")
        with self._booking_lock:
            row = self.handovers.get(handover_id)
            if row is None or row.clinic_id != clinic_id:
                raise ValueError("handover_not_found")
            updated = HandoverRecord(
                id=row.id,
                clinic_id=row.clinic_id,
                voice_session_id=row.voice_session_id,
                reason=row.reason,
                summary=row.summary,
                status=status,
                created_at=row.created_at,
                conversation_id=row.conversation_id,
                callback_contact=row.callback_contact,
            )
            self.handovers[handover_id] = updated
            return updated

    def create_conversation(
        self,
        *,
        clinic_id: UUID,
        voice_session_id: UUID,
        language: str,
        recording_consent: bool,
        retention_until: datetime,
    ) -> ConversationRecord:
        with self._booking_lock:
            for existing in self.conversations.values():
                if existing.voice_session_id == voice_session_id:
                    return existing
            row = ConversationRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                voice_session_id=voice_session_id,
                language=language,
                recording_consent=recording_consent,
                retention_until=retention_until,
                created_at=datetime.now(timezone.utc),
            )
            self.conversations[row.id] = row
            return row

    def get_conversation(self, conversation_id: UUID) -> Optional[ConversationRecord]:
        return self.conversations.get(conversation_id)

    def get_conversation_by_session(self, voice_session_id: UUID) -> Optional[ConversationRecord]:
        for row in self.conversations.values():
            if row.voice_session_id == voice_session_id:
                return row
        return None

    def update_conversation_consent(
        self,
        conversation_id: UUID,
        *,
        recording_consent: bool,
        retention_until: datetime,
    ) -> ConversationRecord:
        with self._booking_lock:
            row = self.conversations.get(conversation_id)
            if row is None:
                raise ValueError("conversation_not_found")
            updated = ConversationRecord(
                id=row.id,
                clinic_id=row.clinic_id,
                voice_session_id=row.voice_session_id,
                language=row.language,
                recording_consent=recording_consent,
                retention_until=retention_until,
                created_at=row.created_at,
                deleted_at=row.deleted_at,
                closed_at=row.closed_at,
            )
            self.conversations[conversation_id] = updated
            return updated

    def list_conversations(
        self, clinic_id: UUID, *, include_deleted: bool = False
    ) -> List[ConversationRecord]:
        rows = [row for row in self.conversations.values() if row.clinic_id == clinic_id]
        if not include_deleted:
            rows = [row for row in rows if row.deleted_at is None]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    def append_conversation_turn(
        self,
        *,
        conversation_id: UUID,
        clinic_id: UUID,
        role: str,
        text: str,
        has_audio_blob: bool = False,
        audio_storage_key: Optional[str] = None,
    ) -> ConversationTurnRecord:
        with self._booking_lock:
            conversation = self.conversations.get(conversation_id)
            if conversation is None or conversation.clinic_id != clinic_id:
                raise ValueError("conversation_not_found")
            if conversation.deleted_at is not None:
                raise ValueError("conversation_deleted")
            sequence = sum(
                1 for turn in self.conversation_turns.values() if turn.conversation_id == conversation_id
            )
            row = ConversationTurnRecord(
                id=uuid4(),
                conversation_id=conversation_id,
                clinic_id=clinic_id,
                sequence=sequence,
                role=role,
                text=text,
                has_audio_blob=has_audio_blob,
                audio_storage_key=audio_storage_key,
                created_at=datetime.now(timezone.utc),
            )
            self.conversation_turns[row.id] = row
            return row

    def list_conversation_turns(self, conversation_id: UUID) -> List[ConversationTurnRecord]:
        rows = [
            row for row in self.conversation_turns.values() if row.conversation_id == conversation_id
        ]
        return sorted(rows, key=lambda row: row.sequence)

    def hard_delete_conversation(self, conversation_id: UUID) -> ConversationRecord:
        """Deletion-on-request: wipe turns + audio keys, keep tombstone for audit."""
        with self._booking_lock:
            row = self.conversations.get(conversation_id)
            if row is None:
                raise ValueError("conversation_not_found")
            to_remove = [
                turn_id
                for turn_id, turn in self.conversation_turns.items()
                if turn.conversation_id == conversation_id
            ]
            for turn_id in to_remove:
                del self.conversation_turns[turn_id]
            tombstone = ConversationRecord(
                id=row.id,
                clinic_id=row.clinic_id,
                voice_session_id=row.voice_session_id,
                language=row.language,
                recording_consent=row.recording_consent,
                retention_until=row.retention_until,
                created_at=row.created_at,
                deleted_at=datetime.now(timezone.utc),
                closed_at=row.closed_at or datetime.now(timezone.utc),
            )
            self.conversations[conversation_id] = tombstone
            return tombstone

    def purge_expired_conversations(
        self, *, clinic_id: UUID, cutoff: datetime
    ) -> Tuple[int, int]:
        with self._booking_lock:
            expired = [
                row
                for row in self.conversations.values()
                if row.clinic_id == clinic_id
                and row.deleted_at is None
                and row.retention_until <= cutoff
            ]
            turns_purged = 0
            for row in expired:
                turn_ids = [
                    turn_id
                    for turn_id, turn in self.conversation_turns.items()
                    if turn.conversation_id == row.id
                ]
                turns_purged += len(turn_ids)
                for turn_id in turn_ids:
                    del self.conversation_turns[turn_id]
                self.conversations[row.id] = ConversationRecord(
                    id=row.id,
                    clinic_id=row.clinic_id,
                    voice_session_id=row.voice_session_id,
                    language=row.language,
                    recording_consent=row.recording_consent,
                    retention_until=row.retention_until,
                    created_at=row.created_at,
                    deleted_at=cutoff,
                    closed_at=row.closed_at or cutoff,
                )
            return len(expired), turns_purged

    def add_tool_audit(
        self,
        *,
        clinic_id: UUID,
        voice_session_id: Optional[UUID],
        tool_name: str,
        accepted: bool,
        reason: Optional[str],
        arguments: dict,
    ) -> ToolAuditRecord:
        with self._booking_lock:
            row = ToolAuditRecord(
                id=uuid4(),
                clinic_id=clinic_id,
                voice_session_id=voice_session_id,
                tool_name=tool_name,
                accepted=accepted,
                reason=reason,
                arguments=arguments,
                created_at=datetime.now(timezone.utc),
            )
            self.tool_audits.append(row)
            return row

    def list_tool_audits(self, clinic_id: UUID, *, limit: int = 100) -> List[ToolAuditRecord]:
        rows = [row for row in self.tool_audits if row.clinic_id == clinic_id]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows[:limit]


ONBOARDING_STEP_KEYS = [
    "clinic_profile",
    "website_url",
    "discover_review",
    "calendar_choice",
    "opening_hours",
    "receptionist",
]
