from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.services.booking_records import (
    AppointmentRecord,
    AvailabilityWindowRecord,
    ConversationRecord,
    ConversationTurnRecord,
    HandoverRecord,
    OnboardingStepRecord,
    ServiceImportDraftRecord,
    ServiceRecord,
    ToolAuditRecord,
    VoiceSessionRecord,
    WebsitePageRecord,
)
from app.services.clinic_store import (
    ActivityEventRecord,
    CalendarProviderConnectionRecord,
    ClinicRecord,
    ConsultationRecord,
    CustomerRecord,
    InMemoryClinicStore,
    IntegrationActivityRecord,
    MembershipRecord,
    OAuthStateRecord,
    WebsiteIntegrationRecord,
)

logger = logging.getLogger(__name__)

_UNDEFINED_TABLE = "42P01"
_EXCLUSION_VIOLATION = "23P01"
_UNIQUE_VIOLATION = "23505"


def _uuid(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def appointment_conflict_from_db_error(exc: BaseException) -> bool:
    code = getattr(exc, "sqlstate", None) or getattr(getattr(exc, "diag", None), "sqlstate", None)
    return code == _EXCLUSION_VIOLATION


def is_undefined_table(exc: BaseException) -> bool:
    code = getattr(exc, "sqlstate", None) or getattr(getattr(exc, "diag", None), "sqlstate", None)
    return code == _UNDEFINED_TABLE


class PostgresClinicStore(InMemoryClinicStore):
    """Durable clinic store — loads into memory, persists mutations to Postgres."""

    # Tables not present in older migration sets — skip load without failing the whole store.
    _OPTIONAL_LOAD_TABLES = frozenset({"oauth_states", "calendar_connections", "calendar_busy_blocks"})

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        super().__init__()
        self._load_all()

    def _connect(self):
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def _load_all(self) -> None:
        with self._connect() as conn:
            for row in conn.execute("select * from public.clinics"):
                clinic = ClinicRecord(
                    id=_uuid(row["id"]),
                    name=row["name"],
                    timezone=row["timezone"],
                    created_at=_dt(row["created_at"]),
                    public_slug=row.get("public_slug") or "",
                    website_url=row.get("website_url"),
                    website_last_error=row.get("website_last_error"),
                    scheduling_mode=row.get("scheduling_mode") or "unset",
                    google_refresh_token_enc=row.get("google_refresh_token_enc"),
                    google_calendar_id=row.get("google_calendar_id"),
                    google_last_sync_at=_dt(row.get("google_last_sync_at")),
                    google_last_error=row.get("google_last_error"),
                    google_status=row.get("google_status") or "disconnected",
                )
                self.clinics[clinic.id] = clinic
                if clinic.public_slug:
                    self.clinics_by_slug[clinic.public_slug] = clinic.id
            for row in conn.execute("select * from public.clinic_members"):
                membership = MembershipRecord(
                    clinic_id=_uuid(row["clinic_id"]),
                    user_id=_uuid(row["user_id"]),
                    role=row["role"],
                    created_at=_dt(row["created_at"]),
                )
                self.memberships_by_user[membership.user_id] = membership
                self.memberships_by_clinic.setdefault(membership.clinic_id, []).append(membership)
            self._load_table(conn, "website_integrations", self._load_integration)
            self._load_table(conn, "customers", self._load_customer)
            self._load_table(conn, "consultations", self._load_consultation)
            self._load_table(conn, "integration_activity", self._load_integration_activity)
            self._load_table(conn, "activity_events", self._load_activity_event)
            self._load_table(conn, "clinic_services", self._load_service)
            self._load_table(conn, "availability_windows", self._load_availability)
            self._load_table(conn, "appointments", self._load_appointment)
            self._load_table(conn, "voice_sessions", self._load_voice_session)
            self._load_table(conn, "handovers", self._load_handover)
            self._load_table(conn, "conversations", self._load_conversation)
            self._load_table(conn, "conversation_turns", self._load_conversation_turn)
            self._load_table(conn, "tool_audit_events", self._load_tool_audit)
            self._load_table(conn, "service_import_drafts", self._load_import_draft)
            self._load_table(conn, "website_pages", self._load_website_page)
            self._load_table(conn, "onboarding_steps", self._load_onboarding_step)
            self._load_table(conn, "oauth_states", self._load_oauth_state, optional=True)
            self._load_table(conn, "calendar_connections", self._load_calendar_connection, optional=True)

    def _load_table(self, conn, table: str, handler, *, optional: bool = False) -> None:
        try:
            for row in conn.execute(sql.SQL("select * from public.{}").format(sql.Identifier(table))):
                handler(row)
        except psycopg.Error as exc:
            if optional or table in self._OPTIONAL_LOAD_TABLES:
                if is_undefined_table(exc):
                    logger.info("optional table %s not present — skipping load", table)
                    return
            if is_undefined_table(exc):
                logger.warning("table %s missing during load — skipping", table)
                return
            logger.exception("failed loading table %s", table)
            raise

    def _load_integration(self, row) -> None:
        record = WebsiteIntegrationRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            key_hash=row["key_hash"],
            key_prefix=row["key_prefix"],
            label=row["label"],
            revoked_at=_dt(row.get("revoked_at")),
            created_at=_dt(row["created_at"]),
        )
        self.integrations[record.id] = record
        self.integrations_by_hash[record.key_hash] = record.id

    def _load_customer(self, row) -> None:
        record = CustomerRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            email_normalized=row["email_normalized"],
            full_name=row["full_name"],
            phone_e164=row.get("phone_e164"),
            possible_phone_duplicate=bool(row.get("possible_phone_duplicate")),
            created_at=_dt(row["created_at"]),
        )
        self.customers[record.id] = record
        self.customers_by_clinic_email[(record.clinic_id, record.email_normalized)] = record.id

    def _load_consultation(self, row) -> None:
        record = ConsultationRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            customer_id=_uuid(row["customer_id"]),
            category=row["category"],
            service_external_id=row.get("service_external_id"),
            service_name=row.get("service_name"),
            external_enquiry_id=row["external_enquiry_id"],
            consent_ai_call=row["consent_ai_call"],
            consent_text=row["consent_text"],
            consent_version=row["consent_version"],
            consented_at=_dt(row["consented_at"]),
            source_website=row["source_website"],
            source_submitted_at=_dt(row["source_submitted_at"]),
            idempotency_key=row["idempotency_key"],
            created_at=_dt(row["created_at"]),
        )
        self.consultations[record.id] = record
        self.consultations_by_idempotency[(record.clinic_id, record.idempotency_key)] = record.id

    def _load_integration_activity(self, row) -> None:
        self.activity.append(
            IntegrationActivityRecord(
                id=_uuid(row["id"]),
                clinic_id=_uuid(row["clinic_id"]),
                integration_id=_uuid(row["integration_id"]) if row.get("integration_id") else None,
                status=row["status"],
                reason=row.get("reason"),
                idempotency_key=row.get("idempotency_key"),
                created_at=_dt(row["created_at"]),
            )
        )

    def _load_activity_event(self, row) -> None:
        self.activity_events.append(
            ActivityEventRecord(
                id=_uuid(row["id"]),
                clinic_id=_uuid(row["clinic_id"]),
                actor_type=row["actor_type"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=_uuid(row["entity_id"]) if row.get("entity_id") else None,
                payload=row.get("payload") or {},
                created_at=_dt(row["created_at"]),
            )
        )

    def _load_service(self, row) -> None:
        record = ServiceRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            name=row["name"],
            category=row["category"],
            duration_minutes=row["duration_minutes"],
            price_paise=row.get("price_paise"),
            active=row["active"],
            created_at=_dt(row["created_at"]),
            source_url=row.get("source_url"),
            imported_at=_dt(row.get("imported_at")),
        )
        self.services[record.id] = record

    def _load_availability(self, row) -> None:
        self.availability.append(
            AvailabilityWindowRecord(
                id=_uuid(row["id"]),
                clinic_id=_uuid(row["clinic_id"]),
                weekday=row["weekday"],
                start_minute=row["start_minute"],
                end_minute=row["end_minute"],
                created_at=_dt(row["created_at"]),
            )
        )

    def _load_appointment(self, row) -> None:
        record = AppointmentRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            customer_id=_uuid(row["customer_id"]),
            service_id=_uuid(row["service_id"]),
            starts_at_utc=_dt(row["starts_at_utc"]),
            ends_at_utc=_dt(row["ends_at_utc"]),
            status=row["status"],
            created_at=_dt(row["created_at"]),
            idempotency_key=row.get("idempotency_key"),
            provider=row.get("provider") or "lala",
            sync_status=row.get("sync_status") or "local",
            external_event_id=row.get("external_event_id"),
            voice_session_id=_uuid(row["voice_session_id"]) if row.get("voice_session_id") else None,
        )
        self.appointments[record.id] = record

    def _load_voice_session(self, row) -> None:
        record = VoiceSessionRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            language=row["language"],
            recording_consent=row["recording_consent"],
            status=row["status"],
            created_at=_dt(row["created_at"]),
            closed_at=_dt(row.get("closed_at")),
            visitor_token=row.get("visitor_token"),
            actor_type=row.get("actor_type") or "owner",
            customer_id=_uuid(row["customer_id"]) if row.get("customer_id") else None,
            customer_verified_at=_dt(row.get("customer_verified_at")),
            pending_email=row.get("pending_email"),
            pending_phone=row.get("pending_phone"),
            pending_full_name=row.get("pending_full_name"),
            verification_code_hash=row.get("verification_code_hash"),
            verification_expires_at=_dt(row.get("verification_expires_at")),
            verification_attempts=int(row.get("verification_attempts") or 0),
            selected_service_id=_uuid(row["selected_service_id"])
            if row.get("selected_service_id")
            else None,
            selected_starts_at_utc=_dt(row.get("selected_starts_at_utc")),
            callback_contact=row.get("callback_contact"),
            consent_version=row.get("consent_version"),
            consent_recorded_at=_dt(row.get("consent_recorded_at")),
        )
        self.voice_sessions[record.id] = record

    def _load_handover(self, row) -> None:
        record = HandoverRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            voice_session_id=_uuid(row["voice_session_id"]) if row.get("voice_session_id") else None,
            reason=row["reason"],
            summary=row["summary"],
            status=row["status"],
            created_at=_dt(row["created_at"]),
            conversation_id=_uuid(row["conversation_id"]) if row.get("conversation_id") else None,
            callback_contact=row.get("callback_contact"),
        )
        self.handovers[record.id] = record

    def _load_conversation(self, row) -> None:
        record = ConversationRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            voice_session_id=_uuid(row["voice_session_id"]),
            language=row["language"],
            recording_consent=row["recording_consent"],
            retention_until=_dt(row["retention_until"]),
            created_at=_dt(row["created_at"]),
            deleted_at=_dt(row.get("deleted_at")),
            closed_at=_dt(row.get("closed_at")),
        )
        self.conversations[record.id] = record

    def _load_conversation_turn(self, row) -> None:
        record = ConversationTurnRecord(
            id=_uuid(row["id"]),
            conversation_id=_uuid(row["conversation_id"]),
            clinic_id=_uuid(row["clinic_id"]),
            sequence=row["sequence"],
            role=row["role"],
            text=row["text"],
            has_audio_blob=row.get("has_audio_blob", False),
            audio_storage_key=row.get("audio_storage_key"),
            created_at=_dt(row["created_at"]),
        )
        self.conversation_turns[record.id] = record

    def _load_tool_audit(self, row) -> None:
        self.tool_audits.append(
            ToolAuditRecord(
                id=_uuid(row["id"]),
                clinic_id=_uuid(row["clinic_id"]),
                voice_session_id=_uuid(row["voice_session_id"]) if row.get("voice_session_id") else None,
                tool_name=row["tool_name"],
                accepted=row["accepted"],
                reason=row.get("reason"),
                arguments=row.get("arguments") or {},
                created_at=_dt(row["created_at"]),
            )
        )

    def _load_import_draft(self, row) -> None:
        record = ServiceImportDraftRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            name=row.get("name"),
            description=row.get("description"),
            duration_minutes=row.get("duration_minutes"),
            price_paise=row.get("price_paise"),
            currency=row.get("currency"),
            category=row.get("category"),
            source_url=row.get("source_url"),
            imported_at=_dt(row["imported_at"]),
            status=row.get("status") or "pending",
        )
        self.import_drafts[record.id] = record

    def _load_website_page(self, row) -> None:
        record = WebsitePageRecord(
            id=_uuid(row["id"]),
            clinic_id=_uuid(row["clinic_id"]),
            url=row["url"],
            title=row["title"],
            fetched_at=_dt(row["fetched_at"]),
            body_excerpt=row.get("body_excerpt") or "",
        )
        self.website_pages[record.id] = record

    def _load_onboarding_step(self, row) -> None:
        clinic_id = _uuid(row["clinic_id"])
        key = row["step_key"]
        self.onboarding_steps[(clinic_id, key)] = OnboardingStepRecord(
            clinic_id=clinic_id,
            step_key=key,
            status=row["status"],
            detail=row.get("detail"),
            error=row.get("error"),
            updated_at=_dt(row.get("updated_at")),
        )

    def _load_oauth_state(self, row) -> None:
        record = OAuthStateRecord(
            state=row["state"],
            clinic_id=_uuid(row["clinic_id"]),
            user_id=_uuid(row["user_id"]),
            provider=row["provider"],
            expires_at=_dt(row["expires_at"]),
            created_at=_dt(row["created_at"]),
        )
        self.oauth_states[record.state] = record

    def _load_calendar_connection(self, row) -> None:
        record = CalendarProviderConnectionRecord(
            clinic_id=_uuid(row["clinic_id"]),
            provider=row["provider"],
            api_key_enc=row.get("api_key_enc"),
            status=row.get("status") or "disconnected",
            last_sync_at=_dt(row.get("last_sync_at")),
            last_error=row.get("last_error"),
            config=row.get("config") or {},
            webhook_secret=row.get("webhook_secret"),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )
        self.calendar_connections[(record.clinic_id, record.provider)] = record

    def _exec(self, sql_text: str, params: tuple = ()) -> None:
        with self._connect() as conn:
            conn.execute(sql_text, params)
            conn.commit()

    def _exec_transaction(self, statements: List[Tuple[str, tuple]]) -> None:
        with self._connect() as conn:
            for sql_text, params in statements:
                conn.execute(sql_text, params)
            conn.commit()

    def create_clinic_for_owner(
        self, *, user_id: UUID, name: str, timezone_name: str
    ) -> Tuple[ClinicRecord, MembershipRecord]:
        clinic, membership = super().create_clinic_for_owner(
            user_id=user_id, name=name, timezone_name=timezone_name
        )
        steps = self.list_onboarding_steps(clinic.id)
        statements: List[Tuple[str, tuple]] = [
            (
                """
                insert into public.clinics (
                  id, name, timezone, created_at, public_slug, website_url, website_last_error,
                  scheduling_mode, google_refresh_token_enc, google_calendar_id, google_last_sync_at,
                  google_last_error, google_status
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    clinic.id,
                    clinic.name,
                    clinic.timezone,
                    clinic.created_at,
                    clinic.public_slug,
                    clinic.website_url,
                    clinic.website_last_error,
                    clinic.scheduling_mode,
                    clinic.google_refresh_token_enc,
                    clinic.google_calendar_id,
                    clinic.google_last_sync_at,
                    clinic.google_last_error,
                    clinic.google_status,
                ),
            ),
            (
                "insert into public.clinic_members (clinic_id, user_id, role, created_at) values (%s,%s,%s,%s)",
                (membership.clinic_id, membership.user_id, membership.role, membership.created_at),
            ),
        ]
        for step in steps:
            statements.append(
                (
                    """
                    insert into public.onboarding_steps
                      (clinic_id, step_key, status, detail, error, updated_at)
                    values (%s,%s,%s,%s,%s,%s)
                    on conflict (clinic_id, step_key) do update set
                      status=excluded.status, detail=excluded.detail,
                      error=excluded.error, updated_at=excluded.updated_at
                    """,
                    (step.clinic_id, step.step_key, step.status, step.detail, step.error, step.updated_at),
                )
            )
        self._exec_transaction(statements)
        return clinic, membership

    def update_clinic(self, clinic_id: UUID, **fields: Any) -> ClinicRecord:
        updated = super().update_clinic(clinic_id, **fields)
        self._exec(
            """
            update public.clinics set
              name=%s, timezone=%s, public_slug=%s, website_url=%s, website_last_error=%s,
              scheduling_mode=%s, google_refresh_token_enc=%s, google_calendar_id=%s,
              google_last_sync_at=%s, google_last_error=%s, google_status=%s
            where id=%s
            """,
            (
                updated.name,
                updated.timezone,
                updated.public_slug,
                updated.website_url,
                updated.website_last_error,
                updated.scheduling_mode,
                updated.google_refresh_token_enc,
                updated.google_calendar_id,
                updated.google_last_sync_at,
                updated.google_last_error,
                updated.google_status,
                updated.id,
            ),
        )
        return updated

    def _upsert_onboarding_step_row(self, step: OnboardingStepRecord) -> None:
        self._exec(
            """
            insert into public.onboarding_steps
              (clinic_id, step_key, status, detail, error, updated_at)
            values (%s,%s,%s,%s,%s,%s)
            on conflict (clinic_id, step_key) do update set
              status=excluded.status, detail=excluded.detail, error=excluded.error, updated_at=excluded.updated_at
            """,
            (step.clinic_id, step.step_key, step.status, step.detail, step.error, step.updated_at),
        )

    def upsert_onboarding_step(self, **kwargs) -> OnboardingStepRecord:
        row = super().upsert_onboarding_step(**kwargs)
        self._upsert_onboarding_step_row(row)
        return row

    def save_oauth_state(self, **kwargs) -> OAuthStateRecord:
        row = super().save_oauth_state(**kwargs)
        try:
            self._exec(
                """
                insert into public.oauth_states (state, clinic_id, user_id, provider, expires_at, created_at)
                values (%s,%s,%s,%s,%s,%s)
                on conflict (state) do update set
                  clinic_id=excluded.clinic_id, user_id=excluded.user_id,
                  provider=excluded.provider, expires_at=excluded.expires_at
                """,
                (row.state, row.clinic_id, row.user_id, row.provider, row.expires_at, row.created_at),
            )
        except psycopg.Error as exc:
            if is_undefined_table(exc):
                logger.info("oauth_states table missing — in-memory state only")
            else:
                raise
        return row

    def take_oauth_state(self, state: str) -> Optional[OAuthStateRecord]:
        row = super().take_oauth_state(state)
        try:
            self._exec("delete from public.oauth_states where state = %s", (state,))
        except psycopg.Error as exc:
            if not is_undefined_table(exc):
                raise
        return row

    def upsert_calendar_provider_connection(self, **kwargs) -> CalendarProviderConnectionRecord:
        row = super().upsert_calendar_provider_connection(**kwargs)
        try:
            self._exec(
                """
                insert into public.calendar_connections (
                  clinic_id, provider, api_key_enc, status, last_sync_at, last_error, config,
                  webhook_secret, created_at, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (clinic_id, provider) do update set
                  api_key_enc=excluded.api_key_enc, status=excluded.status,
                  last_sync_at=excluded.last_sync_at, last_error=excluded.last_error,
                  config=excluded.config, webhook_secret=excluded.webhook_secret,
                  updated_at=excluded.updated_at
                """,
                (
                    row.clinic_id,
                    row.provider,
                    row.api_key_enc,
                    row.status,
                    row.last_sync_at,
                    row.last_error,
                    Json(row.config),
                    row.webhook_secret,
                    row.created_at,
                    row.updated_at,
                ),
            )
        except psycopg.Error as exc:
            if is_undefined_table(exc):
                logger.info("calendar_connections table missing — in-memory only")
            else:
                raise
        return row

    def create_website_integration(self, **kwargs) -> WebsiteIntegrationRecord:
        row = super().create_website_integration(**kwargs)
        self._exec(
            """
            insert into public.website_integrations
              (id, clinic_id, key_hash, key_prefix, label, revoked_at, created_at)
            values (%s,%s,%s,%s,%s,%s,%s)
            """,
            (row.id, row.clinic_id, row.key_hash, row.key_prefix, row.label, row.revoked_at, row.created_at),
        )
        return row

    def revoke_website_integration(self, **kwargs) -> WebsiteIntegrationRecord:
        row = super().revoke_website_integration(**kwargs)
        self._exec(
            "update public.website_integrations set revoked_at=%s where id=%s",
            (row.revoked_at, row.id),
        )
        return row

    def upsert_customer_by_email(self, **kwargs) -> Tuple[CustomerRecord, str]:
        row, outcome = super().upsert_customer_by_email(**kwargs)
        self._exec(
            """
            insert into public.customers
              (id, clinic_id, email_normalized, full_name, phone_e164, possible_phone_duplicate, created_at)
            values (%s,%s,%s,%s,%s,%s,%s)
            on conflict (clinic_id, email_normalized) do update set
              phone_e164=coalesce(public.customers.phone_e164, excluded.phone_e164),
              possible_phone_duplicate=excluded.possible_phone_duplicate
            """,
            (
                row.id,
                row.clinic_id,
                row.email_normalized,
                row.full_name,
                row.phone_e164,
                row.possible_phone_duplicate,
                row.created_at,
            ),
        )
        return row, outcome

    def create_consultation(self, **kwargs) -> ConsultationRecord:
        row = super().create_consultation(**kwargs)
        self._exec(
            """
            insert into public.consultations (
              id, clinic_id, customer_id, category, service_external_id, service_name,
              external_enquiry_id, consent_ai_call, consent_text, consent_version, consented_at,
              source_website, source_submitted_at, idempotency_key, created_at
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.clinic_id,
                row.customer_id,
                row.category,
                row.service_external_id,
                row.service_name,
                row.external_enquiry_id,
                row.consent_ai_call,
                row.consent_text,
                row.consent_version,
                row.consented_at,
                row.source_website,
                row.source_submitted_at,
                row.idempotency_key,
                row.created_at,
            ),
        )
        return row

    def add_integration_activity(self, **kwargs) -> IntegrationActivityRecord:
        row = super().add_integration_activity(**kwargs)
        self._exec(
            """
            insert into public.integration_activity
              (id, clinic_id, integration_id, status, reason, idempotency_key, created_at)
            values (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.clinic_id,
                row.integration_id,
                row.status,
                row.reason,
                row.idempotency_key,
                row.created_at,
            ),
        )
        return row

    def add_activity_event(self, **kwargs) -> ActivityEventRecord:
        row = super().add_activity_event(**kwargs)
        self._exec(
            """
            insert into public.activity_events
              (id, clinic_id, actor_type, action, entity_type, entity_id, payload, created_at)
            values (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.clinic_id,
                row.actor_type,
                row.action,
                row.entity_type,
                row.entity_id,
                Json(row.payload),
                row.created_at,
            ),
        )
        return row

    def create_service(self, **kwargs) -> ServiceRecord:
        row = super().create_service(**kwargs)
        self._exec(
            """
            insert into public.clinic_services
              (id, clinic_id, name, category, duration_minutes, price_paise, active, created_at, source_url, imported_at)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.clinic_id,
                row.name,
                row.category,
                row.duration_minutes,
                row.price_paise,
                row.active,
                row.created_at,
                row.source_url,
                row.imported_at,
            ),
        )
        return row

    def add_availability_window(self, **kwargs) -> AvailabilityWindowRecord:
        row = super().add_availability_window(**kwargs)
        self._exec(
            """
            insert into public.availability_windows
              (id, clinic_id, weekday, start_minute, end_minute, created_at)
            values (%s,%s,%s,%s,%s,%s)
            """,
            (row.id, row.clinic_id, row.weekday, row.start_minute, row.end_minute, row.created_at),
        )
        return row

    def _persist_appointment_row(self, row: AppointmentRecord) -> None:
        self._exec(
            """
            insert into public.appointments (
              id, clinic_id, customer_id, service_id, starts_at_utc, ends_at_utc, status, created_at,
              idempotency_key, provider, sync_status, external_event_id, voice_session_id
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.clinic_id,
                row.customer_id,
                row.service_id,
                row.starts_at_utc,
                row.ends_at_utc,
                row.status,
                row.created_at,
                row.idempotency_key,
                row.provider,
                row.sync_status,
                row.external_event_id,
                row.voice_session_id,
            ),
        )

    def create_appointment(self, **kwargs) -> AppointmentRecord:
        row = super().create_appointment(**kwargs)
        try:
            self._persist_appointment_row(row)
        except psycopg.Error as exc:
            self.appointments.pop(row.id, None)
            if appointment_conflict_from_db_error(exc):
                raise ValueError("appointment_conflict") from exc
            if getattr(exc, "sqlstate", None) == _UNIQUE_VIOLATION and row.idempotency_key:
                existing = self.get_appointment_by_idempotency(
                    clinic_id=row.clinic_id, idempotency_key=row.idempotency_key
                )
                if existing:
                    return existing
            raise
        return row

    def update_appointment_sync(self, **kwargs) -> AppointmentRecord:
        row = super().update_appointment_sync(**kwargs)
        self._exec(
            """
            update public.appointments
            set provider=%s, sync_status=%s, external_event_id=%s
            where id=%s and clinic_id=%s
            """,
            (row.provider, row.sync_status, row.external_event_id, row.id, row.clinic_id),
        )
        return row

    def cancel_appointment(self, **kwargs) -> AppointmentRecord:
        row = super().cancel_appointment(**kwargs)
        self._exec(
            "update public.appointments set status=%s where id=%s and clinic_id=%s",
            (row.status, row.id, row.clinic_id),
        )
        return row

    def reschedule_appointment(self, **kwargs) -> AppointmentRecord:
        try:
            row = super().reschedule_appointment(**kwargs)
        except ValueError:
            raise
        try:
            self._exec(
                """
                update public.appointments
                set starts_at_utc=%s, ends_at_utc=%s, status=%s
                where id=%s and clinic_id=%s
                """,
                (row.starts_at_utc, row.ends_at_utc, row.status, row.id, row.clinic_id),
            )
        except psycopg.Error as exc:
            if appointment_conflict_from_db_error(exc):
                raise ValueError("appointment_conflict") from exc
            raise
        return row

    def _voice_session_params(self, row: VoiceSessionRecord) -> tuple:
        return (
            row.id,
            row.clinic_id,
            row.language,
            row.recording_consent,
            row.status,
            row.created_at,
            row.closed_at,
            row.visitor_token,
            row.actor_type,
            row.customer_id,
            row.customer_verified_at,
            row.pending_email,
            row.pending_phone,
            row.pending_full_name,
            row.verification_code_hash,
            row.verification_expires_at,
            row.verification_attempts,
            row.selected_service_id,
            row.selected_starts_at_utc,
            row.callback_contact,
            row.consent_version,
            row.consent_recorded_at,
        )

    def create_voice_session(self, **kwargs) -> VoiceSessionRecord:
        row = super().create_voice_session(**kwargs)
        cols = (
            "id, clinic_id, language, recording_consent, status, created_at, closed_at, visitor_token, "
            "actor_type, customer_id, customer_verified_at, pending_email, pending_phone, pending_full_name, "
            "verification_code_hash, verification_expires_at, verification_attempts, selected_service_id, "
            "selected_starts_at_utc, callback_contact, consent_version, consent_recorded_at"
        )
        placeholders = ", ".join(["%s"] * 22)
        try:
            self._exec(
                f"insert into public.voice_sessions ({cols}) values ({placeholders})",
                self._voice_session_params(row),
            )
        except psycopg.Error as exc:
            if is_undefined_table(exc):
                raise
            # Older schema without extended columns — minimal insert
            if "column" in str(exc).lower():
                self._exec(
                    """
                    insert into public.voice_sessions
                      (id, clinic_id, language, recording_consent, status, created_at, closed_at, visitor_token, actor_type)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        row.id,
                        row.clinic_id,
                        row.language,
                        row.recording_consent,
                        row.status,
                        row.created_at,
                        row.closed_at,
                        row.visitor_token,
                        row.actor_type,
                    ),
                )
            else:
                raise
        return row

    def update_voice_session(self, session_id: UUID, **fields) -> VoiceSessionRecord:
        row = super().update_voice_session(session_id, **fields)
        try:
            self._exec(
                """
                update public.voice_sessions set
                  language=%s, recording_consent=%s, status=%s, closed_at=%s,
                  customer_id=%s, customer_verified_at=%s, pending_email=%s, pending_phone=%s,
                  pending_full_name=%s, verification_code_hash=%s, verification_expires_at=%s,
                  verification_attempts=%s, selected_service_id=%s, selected_starts_at_utc=%s,
                  callback_contact=%s, consent_version=%s, consent_recorded_at=%s
                where id=%s
                """,
                (
                    row.language,
                    row.recording_consent,
                    row.status,
                    row.closed_at,
                    row.customer_id,
                    row.customer_verified_at,
                    row.pending_email,
                    row.pending_phone,
                    row.pending_full_name,
                    row.verification_code_hash,
                    row.verification_expires_at,
                    row.verification_attempts,
                    row.selected_service_id,
                    row.selected_starts_at_utc,
                    row.callback_contact,
                    row.consent_version,
                    row.consent_recorded_at,
                    row.id,
                ),
            )
        except psycopg.Error as exc:
            if "column" in str(exc).lower():
                self._exec(
                    """
                    update public.voice_sessions
                    set language=%s, recording_consent=%s, status=%s, closed_at=%s
                    where id=%s
                    """,
                    (row.language, row.recording_consent, row.status, row.closed_at, row.id),
                )
            else:
                raise
        return row

    def create_handover(self, **kwargs) -> HandoverRecord:
        row = super().create_handover(**kwargs)
        try:
            self._exec(
                """
                insert into public.handovers
                  (id, clinic_id, voice_session_id, reason, summary, status, created_at, conversation_id, callback_contact)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row.id,
                    row.clinic_id,
                    row.voice_session_id,
                    row.reason,
                    row.summary,
                    row.status,
                    row.created_at,
                    row.conversation_id,
                    row.callback_contact,
                ),
            )
        except psycopg.Error as exc:
            if "column" in str(exc).lower() and "callback_contact" in str(exc):
                self._exec(
                    """
                    insert into public.handovers
                      (id, clinic_id, voice_session_id, reason, summary, status, created_at, conversation_id)
                    values (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        row.id,
                        row.clinic_id,
                        row.voice_session_id,
                        row.reason,
                        row.summary,
                        row.status,
                        row.created_at,
                        row.conversation_id,
                    ),
                )
            else:
                raise
        return row

    def set_handover_conversation(self, handover_id: UUID, conversation_id: UUID) -> None:
        super().set_handover_conversation(handover_id, conversation_id)
        row = self.handovers.get(handover_id)
        if row:
            self._exec(
                "update public.handovers set conversation_id=%s where id=%s",
                (conversation_id, handover_id),
            )

    def update_handover_status(self, **kwargs) -> HandoverRecord:
        row = super().update_handover_status(**kwargs)
        self._exec(
            "update public.handovers set status=%s where id=%s and clinic_id=%s",
            (row.status, row.id, row.clinic_id),
        )
        return row

    def create_conversation(self, **kwargs) -> ConversationRecord:
        row = super().create_conversation(**kwargs)
        self._exec(
            """
            insert into public.conversations
              (id, clinic_id, voice_session_id, language, recording_consent, retention_until, created_at, deleted_at, closed_at)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.clinic_id,
                row.voice_session_id,
                row.language,
                row.recording_consent,
                row.retention_until,
                row.created_at,
                row.deleted_at,
                row.closed_at,
            ),
        )
        return row

    def append_conversation_turn(self, **kwargs) -> ConversationTurnRecord:
        row = super().append_conversation_turn(**kwargs)
        self._exec(
            """
            insert into public.conversation_turns
              (id, conversation_id, clinic_id, sequence, role, text, has_audio_blob, audio_storage_key, created_at)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.conversation_id,
                row.clinic_id,
                row.sequence,
                row.role,
                row.text,
                row.has_audio_blob,
                row.audio_storage_key,
                row.created_at,
            ),
        )
        return row

    def hard_delete_conversation(self, conversation_id: UUID) -> ConversationRecord:
        row = super().hard_delete_conversation(conversation_id)
        with self._connect() as conn:
            conn.execute(
                "delete from public.conversation_turns where conversation_id = %s",
                (conversation_id,),
            )
            conn.execute(
                """
                update public.conversations
                set deleted_at=%s, closed_at=coalesce(closed_at, %s)
                where id=%s
                """,
                (row.deleted_at, row.closed_at, conversation_id),
            )
            conn.commit()
        return row

    def purge_expired_conversations(self, *, clinic_id: UUID, cutoff: datetime) -> Tuple[int, int]:
        count, turns = super().purge_expired_conversations(clinic_id=clinic_id, cutoff=cutoff)
        if count == 0:
            return count, turns
        with self._connect() as conn:
            for row in self.conversations.values():
                if row.clinic_id != clinic_id or row.deleted_at is None:
                    continue
                if row.deleted_at != cutoff:
                    continue
                conn.execute(
                    "delete from public.conversation_turns where conversation_id = %s",
                    (row.id,),
                )
                conn.execute(
                    """
                    update public.conversations set deleted_at=%s, closed_at=%s where id=%s
                    """,
                    (row.deleted_at, row.closed_at, row.id),
                )
            conn.commit()
        return count, turns

    def add_tool_audit(self, **kwargs) -> ToolAuditRecord:
        row = super().add_tool_audit(**kwargs)
        self._exec(
            """
            insert into public.tool_audit_events
              (id, clinic_id, voice_session_id, tool_name, accepted, reason, arguments, created_at)
            values (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.clinic_id,
                row.voice_session_id,
                row.tool_name,
                row.accepted,
                row.reason,
                Json(row.arguments),
                row.created_at,
            ),
        )
        return row

    def add_service_import_draft(self, **kwargs) -> ServiceImportDraftRecord:
        row = super().add_service_import_draft(**kwargs)
        self._exec(
            """
            insert into public.service_import_drafts
              (id, clinic_id, name, description, duration_minutes, price_paise, currency, category, source_url, imported_at, status)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row.id,
                row.clinic_id,
                row.name,
                row.description,
                row.duration_minutes,
                row.price_paise,
                row.currency,
                row.category,
                row.source_url,
                row.imported_at,
                row.status,
            ),
        )
        return row

    def update_service_import_draft(self, **kwargs) -> ServiceImportDraftRecord:
        row = super().update_service_import_draft(**kwargs)
        self._exec(
            """
            update public.service_import_drafts set
              name=%s, description=%s, duration_minutes=%s, price_paise=%s, currency=%s,
              category=%s, source_url=%s, status=%s
            where id=%s and clinic_id=%s
            """,
            (
                row.name,
                row.description,
                row.duration_minutes,
                row.price_paise,
                row.currency,
                row.category,
                row.source_url,
                row.status,
                row.id,
                row.clinic_id,
            ),
        )
        return row

    def add_website_page(self, **kwargs) -> WebsitePageRecord:
        row = super().add_website_page(**kwargs)
        self._exec(
            """
            insert into public.website_pages (id, clinic_id, url, title, fetched_at, body_excerpt)
            values (%s,%s,%s,%s,%s,%s)
            """,
            (row.id, row.clinic_id, row.url, row.title, row.fetched_at, row.body_excerpt),
        )
        return row