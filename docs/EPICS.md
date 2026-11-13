# Lala — Development Epics (POC)

Dependency order: 0 → 1 → 2 → 3 → 4A → 4 → 5 → 6 → 7 → 8.

**Recommended first implementation epic after planning: Epic 1** (clinic auth and onboarding). Clinic isolation must exist before enquiries can attach to a clinic. Lumen already saves enquiries locally; the forward path (Epics 2–3) needs a clinic-resolved Lala API. No audit finding justifies reversing that order. Epic 4A (design system) can start after Epic 1’s dashboard scaffold and should land before Epic 4 modules so CRM screens share one visual language.

Status labels: Implemented | Partial | Not started | Blocked.

---

## EPIC 0: Existing Codebase Audit and Architecture Validation

| Field | Value |
|---|---|
| Priority | P0 |
| Complexity | S |
| Milestone | A |
| Current status | **Implemented** |

**Goal:** Confirm Lumen capabilities and Lala greenfield gaps; lock architecture in docs.

**Business value:** Prevents building on invented Lumen behaviour; keeps Lala independent.

**Dependencies:** None.

**Existing reusable functionality (Lumen):**
- `package.json`, `.env.example`
- `app/api/consultations/route.ts`, `app/api/services/route.ts`, `app/api/form-token/route.ts`
- `components/consultation-form.tsx`, `components/lumen-website.tsx`
- `lib/enquiry.ts`, `lib/store.ts`, `lib/api.ts`, `lib/types.ts`
- `supabase/migrations/20261109200000_services_and_enquiries.sql`

**Scope:** Read-only Lumen audit; write `PRD.md`, `EPICS.md`, `POC_ROADMAP.md`, `DEMO_RUNBOOK.md`, `DECISIONS.md`.

**Out of scope:** Product code, Lumen edits, scaffolding.

**User stories:**
- As a product owner, I want an evidence-based audit so that the POC plan matches real code.
- As an engineer, I want a clear folder layout and API contract so that implementation can start without re-discovery.

**Technical tasks:** Preflight; inspect Lumen; document statuses with evidence; propose Lala layout and integration JSON.

**Files likely to change:** `./lala/docs/*` only.

**API / DB changes:** None.

**Acceptance criteria:**
- Five docs exist under `./lala/docs/` (PRD, EPICS, POC_ROADMAP, DEMO_RUNBOOK, DECISIONS).
- PRD §15 table uses only the four status labels with evidence rules.
- No Lumen or non-docs Lala files modified.

**Test scenarios:** File existence checks; spot-check Lumen paths cited.

**Definition of Done:** Docs complete; Jira Epic 0 (KAN-10) and children Done; final chat summary delivered.

---

## EPIC 1: Clinic Authentication and Onboarding

| Field | Value |
|---|---|
| Priority | P0 |
| Complexity | M |
| Milestone | A |
| Current status | **Partial** (API + isolation tests green; live Lala Supabase project blocked by free-tier limit; dashboard source ready, Node not available to run) |

**Goal:** Clinic owners can sign up, log in, and own an isolated clinic tenant.

**Business value:** Foundation for all multi-tenant data.

**Dependencies:** Epic 0.

**Existing reusable functionality:** None in Lala. Lumen has no clinic auth (by design).

**Scope:**
- Supabase Auth for owners
- `clinics` + `clinic_members` tables with RLS
- FastAPI JWT verification and clinic context middleware
- Minimal onboarding: create clinic name + timezone (`Asia/Kolkata` default)

**Out of scope:** Staff invites, org hierarchies, platform admin UI, SSO.

**User stories:**
- As a Clinic Owner, I want to create an account and clinic so that my data is isolated.
- As a Clinic Owner, I want to log in securely so that only I manage my clinic.
- As the system, I want JWT + membership checks so that cross-clinic access is denied.

**Technical tasks:**
1. Scaffold `backend/` FastAPI + `supabase/migrations/` (additive).
2. Auth signup/login via Supabase; verify JWT in FastAPI.
3. Create clinic on first login / onboarding endpoint.
4. Enforce RLS policies on clinic-scoped tables.
5. Backend tests: valid token, wrong clinic, missing membership.

**Files / modules likely to change:**
- `./lala/backend/**`
- `./lala/supabase/migrations/**`
- `./lala/apps/dashboard/` (login/onboarding pages)

**API / DB changes:**
- Tables: `clinics`, `clinic_members`
- Endpoints: `POST /v1/auth/session` (or rely on Supabase client + `GET /v1/me`), `POST /v1/clinics`, `GET /v1/clinics/current`

**Acceptance criteria:**
- Owner A cannot read clinic B via API.
- New owner ends with exactly one clinic membership role `owner`.
- Tokens without membership receive `401`/`403`.

**Test scenarios:** Dual-clinic isolation; expired JWT; timezone default.

**Definition of Done:** Auth + clinic creation tested; dashboard can show authenticated clinic name from API.

---

## EPIC 2: Independent Website Integration API

| Field | Value |
|---|---|
| Priority | P0 |
| Complexity | M |
| Milestone | A |
| Current status | **Not started** |

**Goal:** Per-clinic hashed API keys and authenticated ingest endpoint that resolves clinic from the key only.

**Business value:** Any supported website can push enquiries without living in the Lala repo.

**Dependencies:** Epic 1.

**Existing reusable functionality (Lumen patterns to mirror, not copy as product):**
- Strict JSON allow-list parsing: `lib/enquiry.ts` `parseEnquiry`
- Idempotent submission id: `consultation_enquiries.submission_id`
- Server-only secrets pattern: `.env.example` (no `NEXT_PUBLIC_` DB/secrets)

**Scope:**
- Generate integration key (show once); store hash + prefix
- `POST /v1/integrations/website/consultations` per PRD §12
- Integration activity log (no secrets)
- Dashboard module: Website integrations (create/revoke/view prefix)

**Out of scope:** HMAC signing (P1); auto-adapters for arbitrary CMS; browser-exposed keys.

**User stories:**
- As a Clinic Owner, I want an API key so that my website can send enquiries securely.
- As Lala, I want to resolve the clinic from the key so that clients cannot spoof tenant IDs.
- As a Clinic Owner, I want an activity log so that I can see accepts/rejects.

**Technical tasks:**
1. Migration: `website_integrations`, `integration_activity`.
2. Key generation + hashing (pepper from env, e.g. `LALA_INTEGRATION_KEY_PEPPER`).
3. Auth dependency on Bearer key → `clinic_id`.
4. Strict Pydantic schema; reject unknown fields.
5. Idempotency unique `(clinic_id, idempotency_key)`.
6. Tests: 201/200/400/401; cross-clinic key misuse.

**Files / modules likely to change:**
- `./lala/backend/app/api/integrations/**`
- `./lala/supabase/migrations/**`
- `./lala/apps/dashboard/` integrations UI
- Later Lumen (Epic 3): `app/api/consultations/route.ts`, `lib/store.ts`, migration for `forward_status`

**API / DB changes:** As PRD §11–12. Env names (proposed): `LALA_INTEGRATION_KEY_PEPPER`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET` / JWKS, `DATABASE_URL`.

**Acceptance criteria:**
- Valid key creates consultation for that clinic only.
- Replay with same idempotency key returns `200` and same ids.
- Revoked key → `401`/`403`.
- Activity rows never contain raw keys.

**Test scenarios:** Malformed JSON; unknown fields; missing consent block; duplicate key.

**Definition of Done:** Contract tests green; owner can mint a key in UI.

---

## EPIC 3: Consultation and Customer Synchronisation

| Field | Value |
|---|---|
| Priority | P0 |
| Complexity | M |
| Milestone | A |
| Current status | **Not started** |

**Goal:** Lumen saves locally, forwards to Lala; Lala upserts customers and stores every enquiry without unsafe merges.

**Business value:** Owners see real website demand in Lala CRM.

**Dependencies:** Epic 2.

**Existing reusable functionality (Lumen):**
- `app/api/consultations/route.ts` — insert point after `saveEnquiry`
- `lib/store.ts` `saveEnquiry` — local persistence + receipt `id`
- `lib/types.ts` consent constants
- Migration `consultation_enquiries` — source of `external_enquiry_id`

**Scope:**
- Lala customer dedupe rules (PRD)
- Lala `consultations` + `customers` + activity events
- Lumen: after local save, forward ≤2 attempts; column `forward_status` (`forwarded`|`rejected`|`pending`)
- Visitor success tied to local save only

**Out of scope:** Syncing Lumen services catalog into Lala automatically; bidirectional sync; phone auto-merge.

**User stories:**
- As a Customer, I want my enquiry saved even if Lala is briefly down.
- As a Clinic Owner, I want repeat emails to enrich rather than duplicate customers.
- As an operator, I want each enquiry kept as its own record.

**Technical tasks:**
1. Lala services for customer upsert + consultation insert.
2. Phone E.164 normalisation; possible-duplicate flag only.
3. Lumen migration: `forward_status`, optional `forwarded_at`, `forward_error`.
4. Lumen forward client (server-only env: `LALA_INTEGRATION_URL`, `LALA_INTEGRATION_API_KEY`).
5. Tests on both sides (Lumen forward unit with mocked fetch; Lala dedupe tests).

**Files / modules likely to change:**
- `./lala/backend/app/services/customers.py` (proposed)
- `./lala/backend/app/services/consultations.py`
- `./lumen-website/app/api/consultations/route.ts`
- `./lumen-website/lib/store.ts`
- `./lumen-website/supabase/migrations/<new>_forward_status.sql`
- `./lumen-website/.env.example` (new name entries only)

**API / DB changes:** Additive Lumen column(s); Lala tables per PRD.

**Acceptance criteria:**
- Happy path: Lumen `forward_status=forwarded`; Lala has customer + consultation.
- Lala 500 → Lumen still `201` to browser; status `pending` after retries.
- Lala 400 → `rejected`, no second retry.
- Same email twice → one customer, two consultations; missing phone filled once.

**Test scenarios:** Duplicate idempotency; email case differences; phone-only match does not merge.

**Definition of Done:** End-to-end manual path works with test `DEMO-` payload; automated dedupe tests pass.

---

## EPIC 4A: Design System, Visual Foundation, and Auth UX

| Field | Value |
|---|---|
| Priority | P0 |
| Complexity | M |
| Milestone | A |
| Current status | **Partial** (Epic 1 auth shell + tokens exist; UX/visual pass starts on live login before CRM modules) |

**Goal:** Ship a shared POC visual system **and** clear owner auth UX by hardening the **existing** dashboard login/onboarding (`AuthShell`) first — then extend tokens/shell to CRM modules. Do **not** start with a separate design walkthrough project or Figma-only phase while the login page is already live.

**Business value:** First stakeholder impression is the sign-in screen; coherent auth → clinic create → workspace builds trust before Epic 4 lists ship. Epic 4+ modules reuse the same language.

**Dependencies:** Epic 1 (dashboard login/onboarding already created). Can run in parallel with Epics 2–3.

**Existing reusable functionality:** `./lala/apps/dashboard/components/auth-shell.tsx`, `app/globals.css` tokens, `app/page.tsx`. Do **not** copy Lumen marketing styles into the operations shell.

**Sequence (act on live UI first):**
1. **Auth UX + visual pass on existing login/signup/onboarding** (this epic’s first gate).
2. Extract/confirm shared tokens + primitives from that pass.
3. Authenticated placeholder shell (clinic name in chrome).
4. Only then Epic 4 CRM modules — no big “project design walkthrough” before step 1.

**Scope — UX (owner auth, PRD §7.1 entry):**
- Clear mode: Sign in vs Create account (one primary CTA; mode switch as text, not a second competing button)
- Hierarchy: brand **Lala** → short purpose line → form; clinic name after onboard
- Errors via `aria-live`; busy/disabled states; signup password minimum hint
- Loading session uses the same composition (no blank layout flash)
- Onboarding: create clinic copy + timezone default called out; sign out always available
- Keyboard-first: labels, focus rings, submit on Enter

**Scope — visual / design system:**
- CSS variables for colour, spacing, radius, elevation, focus; light theme default
- Web fonts (display + body) via Next font loader — avoid Inter/Roboto/Arial/system defaults
- Auth composition as one first viewport; form panel only as the interaction surface
- 2–3 intentional motions (e.g. panel enter, focus, mode switch)
- Later: app chrome + primitives for Epic 4 (button, field, table row, status badge, empty/planned, alert)

**Out of scope:** Separate design walkthrough / brand-book project before login ships; Lumen website redesign; dark-mode-first; Figma-only deliverable without code; staff-admin chrome; per-clinic themes beyond clinic name.

**User stories:**
- As a Clinic Owner, I want a clear sign-in / sign-up path so that I can reach my clinic without guessing.
- As a Clinic Owner, I want the first screen to feel like Lala (not a placeholder form) so that I trust the product in a demo.
- As an engineer, I want tokens proven on auth before CRM screens so that Epic 4 does not invent a second style.

**Technical tasks:**
1. Harden UX on existing `AuthShell` (modes, copy, a11y, loading).
2. Refine `globals.css` tokens + load real fonts in `app/layout.tsx`.
3. Document token map briefly in dashboard `README.md`.
4. Authenticated shell placeholder with clinic name (nav labels can be stubs for Epic 4).
5. Extension path for `voice-client` tokens later — do not create that app here.

**Files / modules likely to change:** `./lala/apps/dashboard/components/auth-shell.tsx`, `app/globals.css`, `app/layout.tsx`, `README.md`.

**API / DB changes:** None.

**Acceptance criteria:**
- Logged-out login page: brand-first, one primary CTA, usable mode switch, accessible errors.
- Signup and clinic-create flows share the same visual system.
- After clinic create, clinic name appears in chrome — not “Lumen”.
- Mobile and desktop: no horizontal overflow on auth flows.
- No fabricated metrics on auth or placeholder workspace.

**Test scenarios:** Cold load → login; toggle signup; failed auth error; session restore; create clinic; sign out.

**Definition of Done:** Auth UX/visual gate green on the live login page; tokens documented; Epic 4 can build modules without a new palette. Walkthrough: follow `AUTH_UX_WALKTHROUGH.md` (shipped baseline first — not a pre-build design exercise).

---

## EPIC 4: Operations Dashboard Foundation

| Field | Value |
|---|---|
| Priority | P0 |
| Complexity | L |
| Milestone | A |
| Current status | **Not started** |

**Goal:** Responsive Lala dashboard modules required for Milestone A, with honest empty states for later modules.

**Business value:** Owners can operate the CRM without SQL.

**Dependencies:** Epics 1–3 (read APIs can stub progressively, but A gate needs live enquiry list); **Epic 4A** (use shared shell/primitives — do not invent a second visual language).

**Existing reusable functionality:** Epic 4A design tokens + shell. Lumen UI is a marketing site — do not reuse as dashboard shell.

**Scope (Milestone A modules):** Overview, Consultations/enquiries, Customers, Website integrations, Activity history.  
Show planned/empty for B/C/D modules (Appointments, AI, Analytics, etc.) without fake data.

**Out of scope:** New design-system work (owned by Epic 4A); staff admin; revenue charts.

**User stories:**
- As a Clinic Owner, I want to see new enquiries so that I can follow up.
- As a Clinic Owner, I want customer profiles linked to consultations.
- As a Clinic Owner, I want activity history so that I know what changed.

**Technical tasks:**
1. Scaffold `apps/dashboard` Next.js with auth session against Supabase.
2. Server or BFF calls to FastAPI with JWT.
3. List/detail views bound to real queries.
4. Empty/planned states for non-A modules.
5. Branding from clinic context (name), not hard-coded “Lumen”.

**Files / modules likely to change:** `./lala/apps/dashboard/**`, dashboard-facing FastAPI list endpoints.

**API / DB changes:** `GET /v1/consultations`, `GET /v1/customers/:id`, `GET /v1/activity`.

**Acceptance criteria:**
- New forwarded enquiry appears after refresh (or light polling).
- No fictional stats.
- Logged-out users cannot view CRM pages.

**Test scenarios:** Empty clinic; clinic with one `DEMO-` enquiry; session expiry.

**Definition of Done:** Owner demo path for §7.1 works using UI only.

---

## EPIC 5: Appointment and Calendar Management

| Field | Value |
|---|---|
| Priority | P0 |
| Complexity | L |
| Milestone | B |
| Current status | **Not started** |

**Goal:** Lala is authoritative for appointments; availability-aware booking with conflict rejection.

**Business value:** Moves clinics from enquiry inbox to scheduled care.

**Dependencies:** Epic 4 (customer profile); Epic 1 tenancy.

**Existing reusable functionality:** None. Lumen explicitly has no appointments table.

**Scope:** Services + availability in Lala; create/update appointment status; calendar views; minimal settings (timezone). Conflict prevention in backend transactions.

**Out of scope:** Staff shift scheduling; multi-resource rooms; payments; SMS reminders (beyond stub).

**User stories:**
- As a Clinic Owner, I want to set availability so that bookings are realistic.
- As a Clinic Owner, I want to book from a customer profile so that the enquiry converts.
- As the system, I want to reject overlaps so that double-booking never persists.

**Technical tasks:**
1. Migrations: `services`, availability, `appointments`.
2. Conflict check (`EXCLUDE` or transactional range overlap per clinic).
3. Dashboard calendar + booking forms.
4. Activity events for create/reschedule/cancel.
5. Tests for overlap, timezone display, cross-clinic denial.

**Files / modules likely to change:** `./lala/backend/app/api/appointments/**`, `./lala/apps/dashboard/` appointments & services modules, migrations.

**API / DB changes:** `POST/PATCH /v1/appointments`, `GET /v1/availability`, services CRUD.

**Acceptance criteria:**
- Overlapping booking → `409`/`400` and no row.
- UTC stored; UI shows clinic TZ.
- Unauthorised clinic id in body ignored/rejected.

**Test scenarios:** Back-to-back OK; overlap fail; cancel frees slot.

**Definition of Done:** Milestone B acceptance gate met (see roadmap).

---

## EPIC 6: AI Receptionist and CRM Tool Integration

| Field | Value |
|---|---|
| Priority | P1 |
| Complexity | L |
| Milestone | C |
| Current status | **Blocked** (Gnani API key + Hugging Face Evon access + GPU host for vLLM/SGLang; languages documented, not yet tested in Lala) |

**Goal:** Browser voice receptionist: Gnani STT → self-hosted Evon v3.3 (tool-calling) → Gnani TTS, with every tool call validated by Lala.

**Business value:** Differentiating AI receptionist without abandoning CRM truth or leaking secrets to the browser.

**Dependencies:** Epic 5 (availability/appointments); Gnani console key; HF gated model approval; GPU server (H100/H200/A100 class — not a laptop).

**Existing reusable functionality:** None in Lala/Lumen (no Gnani SDK or env names). Vendor docs document `en-IN` / `hi-IN` / `te-IN` for STT and TTS — **not yet tested in Lala**.

**Scope:**
- `apps/voice-client`: mic capture → WebSocket to FastAPI only (no Gnani/LLM keys in browser)
- FastAPI pipeline: Gnani STT realtime (`gnani-vachana` SDK) → Evon via OpenAI-compatible client (`LLM_BASE_URL` + `LLM_MODEL`) → validate tools → Gnani TTS SSE/realtime → audio back
- Tools (clinic-scoped service identity): list services, check availability, create appointment, reschedule (with verification), escalate. No cross-clinic reads; no deletes
- System prompt: caller language/script; disclose AI; never diagnose/recommend treatment; escalate when unsure
- English, Hindi, Telugu; Evon remains the only target LLM unless explicitly approved otherwise

**Out of scope:** PSTN / Gnani Agent Builder phone products; simulated AI success; hand-rolled Speech HTTP instead of SDK; inventing a hosted Evon API; unbounded LLM DB access; swapping Evon for another model without approval.

**User stories:**
- As a Customer, I want to ask about services and slots by voice in my language.
- As a Clinic Owner, I want the AI limited to approved, backend-validated tools so that data stays safe.
- As a Customer, I want escalation to staff when the AI cannot help.
- As an engineer, I want `LLM_BASE_URL` swappable so the GPU host can change without code changes.

**Technical tasks:**
1. Integrate `gnani-vachana` (`GnaniSTTStreamClient`, TTS stream/realtime clients) with `GNANI_API_KEY` / `GNANI_API_BASE_URL`.
2. Configure OpenAI-compatible client for Evon (`LLM_BASE_URL`, `LLM_MODEL`, optional `LLM_API_KEY`); document GPU serve via vLLM ≥0.12 or SGLang.
3. Flag and resolve HF repo ID: page `gnani/gnani-evon-v3.3-30B-A3B` vs snippets `gnani/gnani-evon-v3.3` — use the ID on the accepted page.
4. Tool API surface with clinic-scoped least-privilege identity; reject invalid/unauthorised tool calls before side effects.
5. Voice WebSocket protocol browser ↔ FastAPI; language/voice env: `GNANI_STT_MODEL`, `GNANI_TTS_MODEL`, `GNANI_TTS_VOICE_{EN,HI,TE}`.
6. Tests with mocked Gnani + mocked LLM; gated live tests only when key + GPU exist. Never call live APIs from CI without secrets.

**Files / modules likely to change:** `./lala/apps/voice-client/**`, `./lala/backend/app/api/voice/**`, `./lala/backend/app/services/gnani_*.py`, `./lala/backend/app/services/llm_evon.py`, env example names only. `HF_TOKEN` stays on GPU host only.

**API / DB changes:** Voice session table; tool audit events; conversation linkage (Epic 7).

**Acceptance criteria:**
- End-to-end turn uses real Gnani STT/TTS and real Evon endpoint (when unblocked).
- Booking via tools hits same conflict logic as dashboard; invalid tool calls never mutate DB.
- Diagnosis/treatment requests refused; AI disclosure present.
- Without consent, no recording persisted.
- If any C blocker remains → clear Blocked state; A+B still runnable.

**Test scenarios:** Tool auth failure; cross-clinic tool denial; language switch; diagnosis refusal; LLM unreachable → graceful escalate.

**Definition of Done:** Live demo with real Gnani + Evon calls; or explicitly deferred with named blockers (key / HF / GPU).

---

## EPIC 7: Conversation Records, Follow-ups and Handover

| Field | Value |
|---|---|
| Priority | P1 |
| Complexity | M |
| Milestone | C |
| Current status | **Not started** |

**Goal:** Persist consented transcripts/recordings metadata, follow-ups, and staff handover inbox.

**Business value:** Owners can audit AI and close the loop on escalations.

**Dependencies:** Epic 6 (or partial if handover created from dashboard only — prefer after voice).

**Existing reusable functionality:** Lumen consent fields as reference for consent shape only.

**Scope:** Conversations list, transcript view, handover inbox, retention job design (90-day default pending confirmation).

**Out of scope:** Full contact-centre QA scoring; long-term data warehouse.

**User stories:**
- As a Clinic Owner, I want to read permitted transcripts so that I can follow up.
- As Clinic Staff (planned role), I want a handover inbox so that escalations are actionable.
- As a Customer, I want deletion/retention respected per policy.

**Technical tasks:** Conversation schema; access checks; handover states; retention deletion approach; dashboard modules for AI receptionist + conversations + handover.

**Files / modules likely to change:** `./lala/backend/app/api/conversations/**`, dashboard AI modules, migrations.

**API / DB changes:** `conversations`, `transcripts`, `handovers`; retention metadata.

**Acceptance criteria:**
- Other clinics cannot fetch transcripts.
- No consent → no audio blob stored.
- Handover visible in inbox after escalation tool.

**Test scenarios:** Cross-tenant transcript fetch denied; retention flag.

**Definition of Done:** C modules show real rows only; empty states otherwise.

---

## EPIC 8: End-to-End POC Testing and Demonstration

| Field | Value |
|---|---|
| Priority | P0 |
| Complexity | M |
| Milestone | D |
| Current status | **Not started** |

**Goal:** Prove multi-clinic isolation and rehearse the demo runbook with real workflows.

**Business value:** Credible POC presentation without fabricated activity.

**Dependencies:** Epics 1–5 minimum; 6–7 if voice is in scope for the presentation.

**Existing reusable functionality:** `DEMO_RUNBOOK.md`; Lumen form + tests when Node available.

**Scope:** Dual-clinic fixtures (synthetic); E2E test for integration ingest; isolation suite; dry-run demo; minimal analytics counts from real tables.

**Out of scope:** Load testing at scale; billing demos.

**User stories:**
- As a stakeholder, I want a 7–10 minute demo that uses real data paths.
- As an engineer, I want an automated isolation test so that regressions are caught.

**Technical tasks:**
1. Proposed E2E: `./lala/backend/app/tests/test_e2e_website_ingest.py` (see final chat summary).
2. Second clinic negative tests.
3. Script checklist aligned to `DEMO_RUNBOOK.md`.
4. Minimal overview counts (enquiries, appointments) from SQL — no fiction.

**Files / modules likely to change:** `./lala/backend/app/tests/**`, possibly tiny analytics endpoint, docs tweaks.

**API / DB changes:** None required beyond prior epics.

**Acceptance criteria:**
- Demo runbook completed once without invented metrics.
- Isolation tests pass.
- Fallback plan exercised at least once in rehearsal.

**Test scenarios:** Full A→B path; B clinic cannot see A; optional C smoke.

**Definition of Done:** Milestone D gate green; known blockers (e.g. Gnani) listed explicitly if C skipped.
