from __future__ import annotations

import re
from typing import List, Tuple
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.models.website import (
    DraftReviewRequest,
    ServiceImportDraftOut,
    WebsiteImportRequest,
    WebsiteKnowledgeOut,
    WebsitePageOut,
)
from app.services import clinics as clinic_service
from app.services import onboarding as onboarding_service
from app.services.clinic_store import ClinicStore
from app.services.url_safety import validate_public_http_url


def _draft_out(row) -> ServiceImportDraftOut:
    return ServiceImportDraftOut(
        id=row.id,
        clinic_id=row.clinic_id,
        name=row.name,
        description=row.description,
        duration_minutes=row.duration_minutes,
        price_paise=row.price_paise,
        currency=row.currency,
        category=row.category,
        source_url=row.source_url,
        imported_at=row.imported_at,
        status=row.status,
    )


def get_knowledge(store: ClinicStore, *, user_id: UUID) -> WebsiteKnowledgeOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    record = store.get_clinic(clinic.id)
    drafts = [row for row in store.list_service_import_drafts(clinic.id) if row.status == "pending"]
    pages = store.list_website_pages(clinic.id)
    last_import = pages[0].fetched_at if pages else None
    return WebsiteKnowledgeOut(
        website_url=record.website_url if record else None,
        last_import_at=last_import,
        last_error=record.website_last_error if record else None,
        pending_drafts=len(drafts),
        pages=[
            WebsitePageOut(url=row.url, title=row.title, fetched_at=row.fetched_at) for row in pages[:20]
        ],
    )


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, flags=re.I)
    return match.group(1).strip() if match else "Untitled page"


def _extract_draft_candidates(html: str) -> List[Tuple[str, str]]:
    """Very small heuristic — treat h2/h3 blocks as service candidates."""
    candidates: List[Tuple[str, str]] = []
    for match in re.finditer(r"<h[23][^>]*>([^<]+)</h[23]>", html, flags=re.I):
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        if 2 <= len(title) <= 120:
            candidates.append((title, "Imported"))
    return candidates[:12]


def import_website(
    store: ClinicStore, *, user_id: UUID, body: WebsiteImportRequest
) -> dict:
    clinic, _ = clinic_service.require_membership(store, user_id)
    try:
        normalized, _host = validate_public_http_url(body.url)
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": code, "message": "Website URL is not allowed"},
        ) from exc
    try:
        response = httpx.get(
            normalized,
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": "LalaWebsiteImporter/0.1"},
        )
        response.raise_for_status()
        html = response.text[:500_000]
    except httpx.HTTPError as exc:
        store.upsert_onboarding_step(
            clinic_id=clinic.id,
            step_key="website_url",
            status="failed",
            error=str(exc),
        )
        store.update_clinic(clinic.id, website_last_error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "import_fetch_failed", "message": "Could not fetch website"},
        ) from exc

    title = _extract_title(html)
    excerpt = re.sub(r"<[^>]+>", " ", html)
    excerpt = re.sub(r"\s+", " ", excerpt).strip()[:4000]
    store.add_website_page(clinic_id=clinic.id, url=normalized, title=title, body_excerpt=excerpt)
    store.update_clinic(clinic.id, website_url=normalized, website_last_error=None)
    store.upsert_onboarding_step(clinic_id=clinic.id, step_key="website_url", status="completed")

    created = 0
    for name, category in _extract_draft_candidates(html):
        store.add_service_import_draft(
            clinic_id=clinic.id,
            name=name,
            description=None,
            duration_minutes=None,
            price_paise=None,
            currency=None,
            category=category,
            source_url=normalized,
        )
        created += 1
    if created:
        store.upsert_onboarding_step(
            clinic_id=clinic.id,
            step_key="discover_review",
            status="incomplete",
            detail=f"{created} draft(s) awaiting review",
        )
    return {
        "drafts_created": created,
        "pages_fetched": 1,
        "website_url": normalized,
    }


def list_drafts(store: ClinicStore, *, user_id: UUID) -> List[ServiceImportDraftOut]:
    clinic, _ = clinic_service.require_membership(store, user_id)
    return [_draft_out(row) for row in store.list_service_import_drafts(clinic.id)]


def review_draft(
    store: ClinicStore, *, user_id: UUID, draft_id: UUID, body: DraftReviewRequest
) -> ServiceImportDraftOut:
    clinic, _ = clinic_service.require_membership(store, user_id)
    draft = store.get_service_import_draft(clinic.id, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "draft_not_found"})
    if body.action == "reject":
        row = store.update_service_import_draft(
            clinic_id=clinic.id, draft_id=draft_id, status="rejected"
        )
        return _draft_out(row)
    if body.action == "merge":
        if body.merge_into_service_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "merge_target_required"},
            )
        row = store.update_service_import_draft(
            clinic_id=clinic.id, draft_id=draft_id, status="merged"
        )
        return _draft_out(row)
    edits = body.edits or {}
    name = str(edits.get("name") or draft.name or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "name_required", "message": "Provide a service name before approving"},
        )
    category = str(edits.get("category") or draft.category or "General")
    duration_raw = edits.get("duration_minutes", draft.duration_minutes)
    if duration_raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "duration_required",
                "message": "Duration is required before a service can be booked or approved",
            },
        )
    duration = int(duration_raw)
    store.create_service(
        clinic_id=clinic.id,
        name=name,
        category=category,
        duration_minutes=duration,
        price_paise=edits.get("price_paise", draft.price_paise),
        source_url=draft.source_url,
        imported_at=draft.imported_at,
    )
    row = store.update_service_import_draft(
        clinic_id=clinic.id, draft_id=draft_id, status="approved"
    )
    pending = [d for d in store.list_service_import_drafts(clinic.id) if d.status == "pending"]
    if not pending:
        store.upsert_onboarding_step(clinic_id=clinic.id, step_key="discover_review", status="completed")
    return _draft_out(row)