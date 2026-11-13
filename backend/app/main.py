from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import clinics, me
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Lala API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(me.router)
app.include_router(clinics.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
