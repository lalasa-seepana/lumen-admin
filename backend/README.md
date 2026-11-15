# Clinic Dial API (Epics 1–4, 6)

FastAPI backend for clinic auth, website ingest, CRM lists, and AI receptionist tools/voice.

## Setup

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Optional live speech: `pip install gnani-vachana` and set `GNANI_API_KEY` + `LLM_BASE_URL`.

## Voice (Epic 6)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/v1/voice/status` | no | Blockers + config flags |
| `POST` | `/v1/voice/sessions` | Bearer JWT | Mint clinic voice session |
| `WS` | `/v1/voice/ws/{session_id}` | session id | Mic/mock audio → STT → Evon tools → TTS |
| `GET` | `/v1/voice/handovers` | Bearer JWT | Escalations for this clinic |

Approved tools only: `list_services`, `check_availability`, `create_appointment`, `reschedule_appointment`, `escalate`.

## Tests

```sh
pytest app/tests/ -q --ignore=app/tests/test_gnani_evon_live.py
# Live smoke (never default CI):
# LALA_LIVE_VOICE=1 GNANI_API_KEY=… LLM_BASE_URL=… pytest app/tests/test_gnani_evon_live.py -q -m live
```
