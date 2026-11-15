# Clinic Dial

Premium SaaS workspace for clinic owners who use an AI receptionist to answer enquiries and manage bookings.

- `apps/dashboard/` — owner workspace (http://localhost:3001)
- `apps/voice-client/` — visitor receptionist (http://127.0.0.1:3002)
- `backend/` — FastAPI
- `supabase/migrations/` — durable schema (wire with `DATABASE_URL`)
- `docs/STATUS.md` — what works vs stubs and external dependencies
- `docs/VOICE_SETUP.md` — visitor voice + provider setup
- `docs/PRD.md` — product requirements
- `docs/DEMO_RUNBOOK.md` — stakeholder demo script
- `docs/TERMINOLOGY.md` — owner/visitor copy terms

## Run locally

```sh
# API
cd backend && source ../.venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Owner workspace
cd apps/dashboard && pnpm dev

# Visitor receptionist
cd apps/voice-client && pnpm dev
```

Configure `backend/.env` and `apps/dashboard/.env.local` (see `.env.example` files).

## Design

Owner UI uses the Clinic Dial design palette: Figtree + EB Garamond, cream `#FFFFEB`, lilac primary `#F0D7FF` with 8px bordered buttons.

## Persistence

Without `DATABASE_URL`, the API uses an in-memory store (tests). Set `DATABASE_URL` to a Clinic Dial Supabase Postgres URL and apply migrations under `supabase/migrations/` for durable data.

## Acceptance path

Owner signs in → creates clinic → reviews website services → configures calendar/hours → visitor requests an appointment → booking is saved → owner sees it in Calendar and Conversations.
