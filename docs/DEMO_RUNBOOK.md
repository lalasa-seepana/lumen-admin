# Clinic Dial — Demo Runbook (7–10 minutes)

Use only real application workflows. Test people: names prefixed `DEMO-`, emails on `example.com`. Never invent completed activity or show fabricated metrics.

**Milestone D gate:** Before a stakeholder room, complete the rehearsal checklist below (automated isolation/E2E + one full dry-run). Default scope is A+B; mock voice + conversations/handover optional; live Gnani/Evon only if D03–D06 are ready (`DECISIONS.md`).

**Auth warm-up (≈2 min):** Sign in / sign up → create clinic if needed → land on Overview. Brand **Clinic Dial** should lead the first viewport; clinic name comes from the API (never hard-coded Lumen).

**Voice:** Prefer mock path unless D03–D06 are ready. Setup notes: `VOICE_SETUP.md`.

---

## Pre-demo gate (Milestone D)

### Automated

```sh
cd backend
../.venv/bin/pytest \
  app/tests/test_e2e_website_ingest.py \
  app/tests/test_tenant_isolation.py \
  app/tests/test_appointments_conflicts.py \
  app/tests/test_availability_tz.py -q
```

Optional broader smoke:

```sh
../.venv/bin/pytest app/tests -q --ignore=app/tests/test_gnani_evon_live.py
```

### Rehearsal (manual)

- [ ] Clinic A: website key → Lumen (or curl) `DEMO-Asha Rao` enquiry → Enquiries + Overview counts match
- [ ] Clinic A: Patients → Book appointment → Calendar shows clinic-TZ time; conflict attempt rejected
- [ ] Clinic B login: Asha **absent**; Overview zeros (or only B’s own `DEMO-` rows)
- [ ] Analytics: counts match Overview + appointments/handovers/conversations from store
- [ ] Fallback plan row exercised once (e.g. skip voice if Gnani blocked — show empty AI state, do not fake transcript)
- [ ] Known C blockers named if voice skipped: Gnani key / HF Evon / GPU (`DECISIONS.md` D03–D06)

Default first stakeholder pass: **A+B + conversations/handover if mock voice used**. Live Gnani/Evon is optional.

---

## Narrative beats

1. What Clinic Dial solves  
2. How an independent clinic website connects  
3. How a customer enquiry enters Clinic Dial  
4. How the owner sees and manages it  
5. Appointments and availability  
6. Tenant isolation (second test clinic)  
7. Where the AI receptionist fits  
8. Implemented vs still planned  

---

## Setup (before the room)

### Apps

| App | Start command | When available |
|---|---|---|
| Lumen | `cd ./lumen-website && pnpm dev` → http://localhost:3000 | Now (existing) |
| Clinic Dial API | `cd ./lala/backend && uvicorn app.main:app --reload --port 8000` | Now |
| Clinic Dial dashboard | `cd ./lala/apps/dashboard && pnpm dev --port 3001` → http://localhost:3001 | Now |
| Clinic Dial voice client | `cd ./lala/apps/voice-client && pnpm dev --port 3002` | Now (mock without Gnani/Evon) |

### Accounts / keys (prepare once)

1. Clinic A owner: `demo-owner-a@example.com` — clinic name e.g. “Demo Clinic A”.  
2. Clinic B owner: `demo-owner-b@example.com` — “Demo Clinic B”.  
3. In Clinic A dashboard → Website integrations → generate key; set Lumen `LALA_INTEGRATION_API_KEY` + `LALA_INTEGRATION_URL` (server-only).  
4. Confirm Lumen `forward_status` column exists (Epic 3).  
5. Optional C: `GNANI_API_KEY` on Clinic Dial backend; Evon reachable at `LLM_BASE_URL` on GPU host; never put keys or `HF_TOKEN` in the browser.

### Data hygiene

- Prefer a clean demo window or filter UI to today’s `DEMO-` rows.  
- Do not open production PII.

---

## Minute-by-minute script

### 0:00–0:45 — Problem and product

**Say:** Clinics already have websites. They need a multi-clinic operations layer for enquiries, customers, and bookings — without mixing tenants. Clinic Dial is that platform. Lumen is only an example clinic site.

**Show:** Clinic Dial dashboard login page (Clinic A), then briefly Lumen homepage.  
**DB:** none yet.

### 0:45–1:45 — Connect an independent website

**Say:** The website never embeds Clinic Dial secrets. The owner creates an integration API key in Clinic Dial; Lumen’s **server** sends `Authorization: Bearer <key>`. Clinic Dial resolves the clinic from the key alone.

**Do:**
1. Logged in as Clinic A → Website integrations.  
2. Show key prefix / “created” state (do not paste full key on screen if recording).  
3. Point at Lumen env **names** only: `LALA_INTEGRATION_URL`, `LALA_INTEGRATION_API_KEY`.

**Expected DB (Clinic A):** `website_integrations` row with `key_hash`, `key_prefix`; no plaintext key stored.

### 1:45–3:30 — Customer enquiry path

**Say:** Visitor stays on Lumen. Lumen saves locally first, then forwards to Clinic Dial.

**Do:**
1. Open Lumen → choose category **Heal Your Mind** → treatment **Aroma Swedish Massage**.  
2. Submit:  
   - Name: `DEMO-Asha Rao`  
   - Email: `demo-asha@example.com`  
   - Phone: optional test number  
   - Consent: checked  
3. Show Lumen success (“enquiry is saved”) + reference id.  
4. (Optional glance) Lumen `consultation_enquiries.forward_status` → `forwarded`.

**Expected DB:**

| System | Table | Fields |
|---|---|---|
| Lumen | `consultation_enquiries` | `full_name`, `email`, `category`, `service_id`, `ai_call_consent`, `forward_status=forwarded` |
| Clinic Dial | `customers` | `email_normalized=demo-asha@example.com`, `full_name` |
| Clinic Dial | `consultations` | linked `customer_id`, `idempotency_key` = Lumen enquiry id |
| Clinic Dial | `integration_activity` | `status=accepted` |
| Clinic Dial | `activity_events` | enquiry received |

### 3:30–5:00 — Owner sees and manages it

**Do:**
1. Clinic Dial dashboard (Clinic A) → Enquiries — open `DEMO-Asha Rao`.  
2. Open patient profile — show consent + enquiry details.  
3. Activity history — point at the new events.

**Say:** Everything here is from the Clinic Dial database, not a mock list.

**Expected DB:** reads only; no new writes unless owner edits.

### 5:00–6:30 — Appointments and availability (Milestone B)

**Do:**
1. Dashboard → Appointments → add service + optional availability window.  
2. From Patients → `DEMO-Asha Rao` → **Book appointment** (or book on Calendar with patient selected).  
3. Attempt a conflicting start → show rejection (`appointment_conflict`).  
4. Refresh Calendar — only the valid appointment remains; times show clinic TZ (`Asia/Kolkata`) with UTC underneath.

**Expected DB / API:**
- `POST /v1/appointments` → one row; conflict → `409`  
- `activity_events`: `appointment.created` (and cancel/reschedule if shown)  
- Analytics appointments count increments from real rows only

### 6:30–8:00 — Tenant isolation

**Do:**
1. Log out → log in as Clinic B.  
2. Enquiries / patients — confirm `DEMO-Asha Rao` is **absent**.  
3. Optional: submit `DEMO-Bala Nair` / `demo-bala@example.com` via a second key or show B’s empty state vs A’s count on Overview (real counts only).

**Expected DB:** Clinic B queries return zero rows for Clinic A ids; RLS + API both deny cross access.

### 8:00–9:00 — AI receptionist fit (Milestone C)

**Say:** Browser voice (not phone lines) streams audio to Clinic Dial. Clinic Dial calls Gnani Speech APIs for STT/TTS and a self-hosted Evon v3.3 LLM for conversation and tool calls. The receptionist only gets authorised CRM tools — same booking rules as the dashboard — and never gives medical advice. Gnani Agent Builder / phone calling is out of scope.

**Do (if C ready):** 60–90s voice ask for availability → book or escalate → show transcript/handover.  
**Do (if C blocked):** Open AI module empty/planned state; name blockers — Gnani API key, Hugging Face Evon access, and/or GPU host.

### 9:00–10:00 — Implemented vs planned + close

**Implemented for this demo (update live):** tick A/B/(C) gates actually shown. Show **Analytics** only as real store counts (consultations, customers, appointments, handovers, conversations) — never revenue fiction.  
**Planned / incomplete:** staff roles UI, HMAC signing, deeper analytics, PSTN, billing, full Google sync, durable Postgres writes (see `STATUS.md`).

**Close:** Clinic Dial is the product; Lumen stays a replaceable website client; CRM appointments stay authoritative in Clinic Dial.

---

## Fallback plan

| Failure | Immediate action | What audience still sees |
|---|---|---|
| Lumen form 503 / DB down | Show prior `DEMO-` enquiry already in Clinic Dial; narrate local-save-first design | Dashboard CRM path |
| Clinic Dial forward pending | Show Lumen `forward_status=pending`; replay forward or POST with curl using server key (off-screen) | Honesty about retry |
| Dashboard auth glitch | Use API GET with owner JWT in terminal (prepared) to list consultations | Data layer still real |
| Appointment conflict UI bug | Show API `409` response from prepared curl | Backend rule holds |
| Gnani / Evon / mic failure | Skip to planned state; do not fake a transcript or simulated AI success | A+B still complete |
| Wrong clinic data appears | **Stop demo**; treat as P0 isolation bug — do not continue with narrative |

---

## Post-demo checklist

- [ ] Revoke any integration key displayed in full.  
- [ ] Leave `DEMO-` rows or delete per retention preference.  
- [ ] Note blockers hit (Gnani, env, etc.) for the engineering backlog.  
- [ ] Confirm no real personal data was used.
