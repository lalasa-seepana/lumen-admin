# Lala — POC Roadmap

Smallest working integration first. Cross-refs: `PRD.md`, `EPICS.md`, `DEMO_RUNBOOK.md`.

Do **not** add billing, elaborate staff scheduling, fake analytics, or unneeded infrastructure.

---

## Milestone overview

| Milestone | Outcome | Epics |
|---|---|---|
| **A** | Lumen form → Lala integration API → Lala CRM → dashboard enquiry | 0 (done), 1, 2, 3, 4A, 4 |
| **B** | Customer profile, availability, appointment create/status | 5 |
| **C** | AI receptionist, CRM tools, conversations / handover | 6, 7 |
| **D** | Multi-clinic isolation proof + presentation | 8 |

Voice (C) is separable: A+B must demo alone if the Gnani API key, Evon HF access, or GPU host is missing.

---

## Milestone A — Website to dashboard enquiry

### Prerequisites (env names)

**Lumen (existing):**
- `SUPABASE_DB_URL`
- `LUMEN_FORM_SECRET`
- `LUMEN_ALLOWED_ORIGINS`
- `LUMEN_TRUSTED_IP_HEADER` (optional)

**Lumen (new for forward):**
- `LALA_INTEGRATION_URL`
- `LALA_INTEGRATION_API_KEY`

**Lala (proposed):**
- `DATABASE_URL` / Supabase DB URL for Lala project
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` (dashboard)
- `SUPABASE_SERVICE_ROLE_KEY` (server only — never browser)
- `SUPABASE_JWT_SECRET` or JWKS URL for FastAPI verification
- `LALA_INTEGRATION_KEY_PEPPER`

**External credentials:** Lala Supabase project (separate from Lumen). No Gnani required.

### Coding sequence

1. Epic 1 — clinic auth + onboarding + RLS  
2. Epic 2 — integration keys + ingest API  
3. Epic 3 — Lala customer/consultation sync + Lumen forward/`forward_status`  
4. Epic 4A — auth UX + visual tokens on **existing login** first (can overlap 2–3); then run `AUTH_UX_WALKTHROUGH.md`  
5. Epic 4 — dashboard A modules (on 4A shell/primitives)  

### Test commands (proposed — Lala code does not exist yet)

```sh
# Lala backend (proposed)
cd ./lala/backend && pytest app/tests/test_auth_isolation.py app/tests/test_integration_ingest.py -q

# Lumen (when Node available)
cd ./lumen-website && pnpm test
```

### Acceptance gate

- [ ] Owner can sign up and open dashboard for their clinic only.  
- [ ] Owner mints integration key (shown once).  
- [ ] Lumen enquiry with `DEMO-` name saves locally and sets `forward_status=forwarded`.  
- [ ] Same enquiry visible in Lala Consultations from DB.  
- [ ] Replay / idempotency returns `200` without duplicate consultation.  
- [ ] Planned modules (appointments, AI, analytics) show empty/planned — no fake rows.

### Remaining dependencies

- None for A beyond Lala Supabase + env configuration.  
- Lumen Node toolchain required to run Lumen tests.

---

## Milestone B — Appointments and availability

### Prerequisites

- Milestone A gate green.  
- Same Lala env as A.  
- Clinic timezone set (default `Asia/Kolkata`).

### Coding sequence

1. Epic 5 — services, availability, appointments, conflict prevention, minimal settings.

### Test commands (proposed)

```sh
cd ./lala/backend && pytest app/tests/test_appointments_conflicts.py app/tests/test_availability_tz.py -q
```

### Acceptance gate

- [ ] Owner creates appointment from customer profile against real availability.  
- [ ] Overlapping booking rejected; DB unchanged for conflict.  
- [ ] Calendar/list reflects DB after refresh.  
- [ ] Activity history records create/update.  
- [ ] Timestamps stored UTC; UI uses clinic TZ.

### Remaining dependencies

- None beyond A. Optional seed of Lala services (can mirror Lumen’s nine treatments manually for demo).

---

## Milestone C — AI receptionist

### Prerequisites

- Milestone B gate green (tools need appointments/availability).  
- **Blocked on (owner = you):**
  1. Gnani API key from https://app.gnani.ai/ (header `X-API-Key-ID`)
  2. Hugging Face access approval for Evon v3.3 (confirm exact repo ID on the page — URL is `gnani/gnani-evon-v3.3-30B-A3B`; snippets often say `gnani/gnani-evon-v3.3`)
  3. GPU host (NVIDIA H100 80GB / H200 / A100, Linux) running vLLM ≥0.12 or SGLang with OpenAI-compatible `/v1/chat/completions` — **not a normal laptop** (cost decision)
- **Server-only env names:** `GNANI_API_KEY`, `GNANI_API_BASE_URL` (default `https://api.vachana.ai`), `GNANI_STT_MODEL` (e.g. `prisma-v3.0`), `GNANI_TTS_MODEL` (e.g. `timbre-v2.5`), `GNANI_TTS_VOICE_EN`, `GNANI_TTS_VOICE_HI`, `GNANI_TTS_VOICE_TE`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` (if protected). `HF_TOKEN` on GPU host only — never in Lala.
- Languages: English, Hindi, Telugu — **documented** for STT and TTS; **not yet tested in Lala**.
- No hosted Evon chat API in Gnani Speech docs — self-host only. Do not use Agent Builder / phone products.

### Coding sequence

1. Epic 6 — voice client WebSocket + `gnani-vachana` SDK + Evon client + authorised CRM tools  
2. Epic 7 — conversations, transcripts, handover inbox, retention design  

### Test commands (proposed)

```sh
cd ./lala/backend && pytest app/tests/test_voice_tools.py app/tests/test_handover.py -q
# Live smoke only when key + GPU Evon exist (never in default CI):
# pytest app/tests/test_gnani_evon_live.py -q -m live
```

### Acceptance gate

- [ ] Browser → FastAPI WebSocket → Gnani STT → Evon tools → Gnani TTS completes in at least one language.  
- [ ] Book/reschedule uses same backend conflict rules as dashboard; invalid tool calls rejected.  
- [ ] Diagnosis/treatment requests refused; AI disclosed.  
- [ ] Transcript/recording only with consent; cross-clinic fetch denied.  
- [ ] Escalation creates handover item.  
- [ ] If any blocker remains: C marked Blocked; A+B demo still passes.

### Remaining dependencies

- Gnani key, HF Evon access, GPU hosting decision/cost.  
- Retention period confirmation (recommend 90 days).

---

## Milestone D — Isolation verification and presentation

### Prerequisites

- A+B complete; C optional.  
- Two test clinics provisioned (synthetic owners).  
- `DEMO_RUNBOOK.md` rehearsed once.

### Coding sequence

1. Epic 8 — E2E ingest test, isolation suite, minimal real analytics counts, demo dry-run.

### Test commands (proposed)

```sh
cd ./lala/backend && pytest app/tests/test_e2e_website_ingest.py app/tests/test_tenant_isolation.py -q
```

### Acceptance gate

- [ ] Clinic B cannot read Clinic A customers/consultations/appointments via API or UI.  
- [ ] Overview counts match SQL aggregates (no fiction).  
- [ ] Full demo runbook executed with `DEMO-` / `example.com` data.  
- [ ] Fallback plan documented and workable if a live step fails.

### Remaining dependencies

- Stakeholder schedule.  
- Explicit call on whether C is in or out of the presentation.

---

## Explicitly deferred (not in A–D build)

- Billing / subscriptions  
- Staff-management UIs and complex org hierarchies  
- HMAC request signing (P1 after A)  
- PSTN telephony  
- Arbitrary website auto-connectors beyond the REST adapter
