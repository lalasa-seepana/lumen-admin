# Clinic Dial — Epic index (POC)

Dependency order completed: 0 → 1 → 2 → 3 → 4A → 4 → 5 → 6 → 7 → 8.

Detailed story/task specs from the POC build are retired. Requirements live in `PRD.md`; live status in `STATUS.md`; open choices in `DECISIONS.md`.

| Epic | Milestone | Status | What it delivered |
|------|-----------|--------|-------------------|
| 0 Audit | A | Implemented | Planning docs + architecture lock |
| 1 Auth / onboarding | A | Implemented | Supabase Auth, clinic create, JWT + membership |
| 2 Website integration API | A | Implemented | Hashed keys, ingest endpoint, clinic resolve |
| 3 Consultation sync | A | Implemented | Customer upsert, enquiry store, Lumen forward + retry |
| 4A Design / auth UX | A | Implemented | Clinic Dial design palette, login/onboarding shell |
| 4 Dashboard CRM | A | Implemented | Overview, enquiries, patients, integrations, activity |
| 5 Appointments | B | Implemented | Services, opening hours, bookings, conflicts |
| 6 Voice receptionist | C | Mock done; live deferred | WebSocket + tools; live needs D03–D06 |
| 7 Conversations / handover | C | Implemented | Transcripts, consent, escalate inbox |
| 8 E2E / isolation / analytics | D | Implemented | Isolation tests, real aggregates, demo gate |

Hardening landed 2026-11-15 (tool-result loop, visitor verification, consent, Postgres writes + overlap migration, Google/Cal.com adapters, mic/text visitor client). Live Gnani/Evon/Google/Cal.com/Postgres restart still need owner credentials — see `STATUS.md` and `VOICE_SETUP.md`.
