from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class OnboardingStepOut(BaseModel):
    key: str
    status: Literal["completed", "incomplete", "failed", "skipped"]
    detail: Optional[str] = None
    error: Optional[str] = None
    updated_at: Optional[datetime] = None


class OnboardingStateOut(BaseModel):
    clinic_name: str
    timezone: str
    website_url: Optional[str] = None
    steps: List[OnboardingStepOut]


class OnboardingClinicUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    timezone: str = Field(min_length=2, max_length=80)