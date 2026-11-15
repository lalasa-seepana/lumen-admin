# Clinic Dial status

Last updated: 2026-11-15

Living status for what works, what is stubbed, and what still needs owner credentials. Product intent: `PRD.md`. Demo: `DEMO_RUNBOOK.md`. Setup: `VOICE_SETUP.md`. Decisions: `DECISIONS.md`. UX gaps: `UX_FUNCTIONAL_AUDIT.md`.

## Capability matrix

| Stage | Capability | Status | Notes |
|-------|------------|--------|-------|
| 1 | Clinic Dial design + CRM workspace | Working | Figtree / EB Garamond |
| 1 | Auth / onboarding | Working | Supabase Auth + onboarding API |
| 2 | Postgres persistence | Implemented (unverified live) | Full SQL writes + overlap exclusion migration; needs `DATABASE_URL` + applied migrations to prove restart survival |
| 2 | Opening hours gate booking | Working | |
| 3 | Website import + Lumen forward | Working | |
| 4 | Calendar UI clinic timezone | Fixed in code | Mock/unit path; browser TZ mismatch addressed via Intl clinic helpers |
| 4 | Google Calendar OAuth | Implemented (unverified live) | Real state + code exchange; never marks connected without token exchange |
| 4 | Cal.com connect + webhook | Implemented (unverified live) | API-key connect + signature verify; needs live key/webhook |
| 5 | Visitor receptionist mic + text | Working (mock speech) | Press-and-hold Talk; text channel; EN/HI/TE selector mid-session |
| 5 | Tool-result → spoken answer loop | Working (mocked LLM) | Failed booking never announced as confirmed |
| 5 | Visitor verification + ownership | Working (mocked) | OTP verify; unauthorized reschedule rejected |
| 5 | Recording consent | Working | Exact label; mid-session withdraw stops future retention |
| 5 | Live Gnani STT/TTS | Dependent | Needs `GNANI_API_KEY`; REST fallback works on Python 3.9 |
| 5 | Live LLM brain | Dependent | **OpenAI recommended** (`LLM_BASE_URL=https://api.openai.com` + `LLM_API_KEY`); Evon/GPU optional |
| 8 | Tenant isolation + analytics | Working | Automated tests |

### Automated tests (mock / in-memory)

```sh
cd backend && ../.venv/bin/pytest app/tests -q --ignore=app/tests/test_gnani_evon_live.py
```

Result in this pass: **67 passed, 1 skipped** (Postgres live test skipped without `DATABASE_URL`).

### Live provider verification (not claimed working)

| Integration | Gate | Status |
|-------------|------|--------|
| Gnani STT/TTS | `GNANI_API_KEY` + reachable `api.vachana.ai` | Not verified |
| OpenAI LLM | `LLM_BASE_URL=https://api.openai.com` + `LLM_API_KEY` + model | Not verified (wired) |
| Evon / LLM | Alternate: GPU host + HF access | Optional; not required when OpenAI is set |
| Google Calendar | `GOOGLE_CLIENT_*` + owner OAuth | Code path present; not verified |
| Cal.com | Clinic API key + webhook secret | Code path present; not verified |
| Postgres restart/isolation | `DATABASE_URL` + migrations applied | Code + migration present; not verified against live DB |
| Real microphone → audible TTS | Live Gnani | Mock silent PCM only without Gnani |

## Environment (placeholders only)

See `backend/.env.example`. Never commit real secrets.

- `DATABASE_URL` — durable store; empty → in-memory (restarts wipe data)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI`
- `CALCOM_API_KEY` / `CALCOM_WEBHOOK_SECRET` (clinic keys stored encrypted per clinic)
- `GNANI_API_KEY` — live STT/TTS
- `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` — live conversation (OpenAI default)
- Speech ≠ reasoning: Gnani alone speaks with a mock brain; OpenAI alone reasons with silent mock TTS

## Noise / languages

- Browser: `echoCancellation` + `noiseSuppression` enabled on `getUserMedia`
- Gnani: language codes `en-IN` / `hi-IN` / `te-IN`; streaming VAD via SDK when live
- **Dedicated Gnani noise-cancellation API parameters are not documented here** — do not invent fields; browser AEC/NS is the fallback

## Remaining external dependencies (precise)

1. **D03** Gnani Speech API key in server env  
2. **D04/D05** Hugging Face Evon access + exact repo ID  
3. **D06** GPU host with OpenAI-compatible Evon at `LLM_BASE_URL`  
4. **D08/D09** TTS voice / model string confirmation for HI/TE  
5. Google Cloud OAuth client for Calendar  
6. Cal.com API key + webhook endpoint reachability  
7. Clinic Dial Supabase Postgres URL + apply `supabase/migrations/` including `20261115160000_voice_calendar_persistence.sql`  
8. Optional object storage for consented audio blobs (transcripts store in DB; audio keys reserved)

## Owner checklist

1. [ ] Apply migrations; set `DATABASE_URL`; restart API; confirm clinic/booking survive restart  
2. [ ] Two-clinic isolation smoke on durable store  
3. [ ] Mint website key → Lumen `DEMO-` enquiry → Enquiries  
4. [ ] Calendar book/reschedule with browser TZ ≠ clinic TZ  
5. [ ] Visitor mock: text + mic (mock STT) booking safety + consent on/off  
6. [ ] Optional live: Gnani + OpenAI → real mic, conversation, audible TTS  
7. [ ] Optional: Google OAuth connect (must not show connected until consent screen completes)  
8. [ ] Optional: Cal.com key + webhook duplicate delivery test  
