from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class IntegrationCreate(BaseModel):
    label: str = Field(default="Website", min_length=1, max_length=80)

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        cleaned = value.strip() or "Website"
        return cleaned[:80]


class IntegrationOut(BaseModel):
    id: UUID
    clinic_id: UUID
    key_prefix: str
    label: str
    revoked_at: Optional[datetime] = None
    created_at: datetime


class IntegrationCreatedOut(IntegrationOut):
    api_key: str = Field(description="Plaintext key shown once. Store hash only after this response.")


class IntegrationActivityOut(BaseModel):
    id: UUID
    clinic_id: UUID
    integration_id: Optional[UUID] = None
    status: Literal["accepted", "duplicate", "rejected"]
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime


class ServiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_call_consent: bool
    consent_text: str = Field(min_length=1, max_length=2000)
    consent_version: str = Field(min_length=1, max_length=120)
    consented_at: datetime


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website: str = Field(min_length=1, max_length=80)
    submitted_at: datetime


class WebsiteConsultationIn(BaseModel):
    """Strict allow-list body for website ingest. Unknown fields → 422/400."""

    model_config = ConfigDict(extra="forbid")

    external_enquiry_id: UUID
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=32)
    category: str = Field(min_length=1, max_length=120)
    service: ServiceIn
    consent: ConsentIn
    source: SourceIn

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("full_name too short")
        return cleaned

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class DedupeOut(BaseModel):
    customer: Literal["created", "existing"]
    possible_phone_duplicate: bool = False


class WebsiteConsultationOut(BaseModel):
    consultation_id: UUID
    customer_id: UUID
    status: Literal["accepted", "duplicate"]
    dedupe: DedupeOut
