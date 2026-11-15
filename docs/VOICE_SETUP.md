# Voice receptionist setup

## Local (mock speech — no provider keys)

1. Start API: `cd backend && source ../.venv/bin/activate && uvicorn app.main:app --reload --port 8000`
2. Start visitor UI: `cd apps/voice-client && pnpm dev` → http://127.0.0.1:3002
3. Open `/?clinic=<public_slug_or_uuid>` from the owner Receptionist page link  
   Local demo (in-memory): http://127.0.0.1:3002/?clinic=lumen-demo
4. Start conversation → type a message **or** press and hold **Talk to receptionist**
5. Without `GNANI_API_KEY` and OpenAI (`LLM_BASE_URL` + `LLM_API_KEY`), the UI shows **Demo mode** / speech-only mock brain

### Consent

Checkbox (unchecked by default):

> I agree to save this conversation's audio recording and transcript.

Toggling mid-session updates the server. Withdrawal stops **future** retention; prior consented turns remain until retention purge or deletion-on-request.

### Languages

Selector: English / Hindi / Telugu (`en-IN`, `hi-IN`, `te-IN`). Changing language mid-session sends `set_language` over the WebSocket; context is preserved in conversation history.

## Live speech + conversation (credentials required)

Copy placeholders from `backend/.env.example`:

```sh
# Speech — Gnani
GNANI_API_KEY=...
GNANI_API_BASE_URL=https://api.vachana.ai
GNANI_STT_MODEL=prisma-v3.0
GNANI_TTS_MODEL=timbre-v2.5
GNANI_TTS_VOICE_EN=Kaveri
GNANI_TTS_VOICE_HI=Nalini
GNANI_TTS_VOICE_TE=Suhana

# Brain — OpenAI (no GPU)
LLM_BASE_URL=https://api.openai.com
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

- **Speech only:** `GNANI_API_KEY` alone → audible replies with mock brain (`mode: speech_only`).
- **Full live conversation:** Gnani + OpenAI → `mode: configured` / WebSocket `mode: live`.
- **Latency (v1):** short system prompt, last-8 history turns, approved clinic facts injected, sentence-chunk TTS (`audio_chunk` then full `turn`).
- **Knowledge (v1 / RAG-lite):** `get_clinic_knowledge` + prompt card from services/hours — no vector DB yet.
- Optional Evon: point `LLM_BASE_URL` at your vLLM/SGLang host and set `LLM_MODEL` to the Evon model id.
- LLM alone without Gnani keeps silent mock TTS.

Live smoke (manual, never default CI):

```sh
cd backend && ../.venv/bin/pytest app/tests/test_gnani_evon_live.py -q -m live
```

## Noise handling

- Browser: `echoCancellation`, `noiseSuppression`, `autoGainControl` on `getUserMedia`
- Do **not** invent Gnani “noise cancellation” request fields; dedicated cancellation is **not documented** in this integration
- Streaming STT uses the provider language code; short/ambiguous utterances may need the language override

## Durable data

1. Create a Clinic Dial Supabase project (separate from Lumen)
2. Apply all files under `supabase/migrations/` in order
3. Set `DATABASE_URL` on the API
4. Restart and confirm bookings/customers/conversations survive

## Calendar providers

- Google: set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`; connect from settings. Connection succeeds only after OAuth code exchange.
- Cal.com: store clinic API key via connect endpoint; set `CALCOM_WEBHOOK_SECRET` for inbound webhooks. Live sync is unverified until credentials exist.

## Safety rules (always on)

- AI disclosure in responses
- No diagnosis / treatment advice → escalate with callback contact when known
- Tool results feed back into the model before the spoken answer
- Booking confirmation requires accepted `create_appointment` with `appointment_id` and status `booked`/`rescheduled`
- Visitor must be verified before changing another person’s appointment
- Explicit confirmation required before visitor booking/reschedule/cancel
