# Lala

Multi-clinic AI receptionist and operations platform (POC).

- `docs/` — PRD, epics, roadmap, demo runbook, decisions
- `backend/` — FastAPI (Epic 1+)
- `supabase/migrations/` — Lala schema (separate project from Lumen)
- `apps/dashboard/` — clinic owner dashboard

Lumen (`../lumen-website` or sibling checkout) is an independent example clinic site, not this product.

## Epic 1 quick start

1. Provision a **Lala** Supabase project (do not reuse Lumen’s).
2. Apply `supabase/migrations/20261113220000_clinics_and_members.sql`.
3. Configure `backend/.env` with `SUPABASE_JWT_SECRET`.
4. Run API: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`
5. Configure `apps/dashboard/.env.local` and run `pnpm dev --port 3001` when Node is available.
