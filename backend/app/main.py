from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    appointments,
    calendar_providers,
    clinics,
    conversations,
    crm,
    integrations,
    me,
    onboarding,
    visitor,
    voice,
    website,
)
from app.core.config import get_settings
from app.services.clinic_store import get_clinic_store

settings = get_settings()
DEMO_OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")
DEMO_SLUG = "lumen-demo"


def _seed_local_demo_clinic() -> None:
    """In-memory demo clinic so the visitor UI works without owner signup first."""
    if settings.database_configured:
        return
    store = get_clinic_store()
    existing = store.get_clinic_by_slug(DEMO_SLUG)
    if existing is not None:
        return
    clinic, _ = store.create_clinic_for_owner(
        user_id=DEMO_OWNER_ID,
        name="Lumen Demo Clinic",
        timezone_name="Asia/Kolkata",
    )
    # Stable public slug for local visitor links.
    store.update_clinic(clinic.id, public_slug=DEMO_SLUG)
    store.create_service(
        clinic_id=clinic.id,
        name="Aroma Swedish Massage",
        category="Relax",
        duration_minutes=60,
        price_paise=320000,
    )
    store.create_service(
        clinic_id=clinic.id,
        name="Deep Tissue Massage",
        category="Heal Your Mind",
        duration_minutes=60,
        price_paise=380000,
    )
    for weekday in range(0, 5):
        store.add_availability_window(
            clinic_id=clinic.id,
            weekday=weekday,
            start_minute=9 * 60,
            end_minute=17 * 60,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _seed_local_demo_clinic()
    yield


app = FastAPI(title="Clinic Dial API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins
    or ["http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(me.router)
app.include_router(clinics.router)
app.include_router(integrations.router)
app.include_router(crm.router)
app.include_router(appointments.router)
app.include_router(voice.router)
app.include_router(conversations.router)
app.include_router(onboarding.router)
app.include_router(website.router)
app.include_router(calendar_providers.router)
app.include_router(visitor.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
