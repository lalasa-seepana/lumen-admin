# Lala API (Epic 1)

FastAPI backend for clinic auth context and onboarding.

## Setup

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set SUPABASE_JWT_SECRET from a Lala Supabase project (not Lumen).
uvicorn app.main:app --reload --port 8000
```

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/healthz` | no | Liveness |
| `GET` | `/v1/me` | Bearer JWT | User + optional clinic |
| `POST` | `/v1/clinics` | Bearer JWT | Create clinic (role `owner`, TZ default `Asia/Kolkata`) |
| `GET` | `/v1/clinics/current` | Bearer JWT | Requires membership |
| `GET` | `/v1/clinics/{id}` | Bearer JWT | Same-clinic only |

Signup/login happen in the dashboard via Supabase Auth. This API only verifies JWTs.

## Tests

```sh
cd backend
source .venv/bin/activate
pytest app/tests/test_auth_isolation.py -q
```

Isolation tests use an in-memory store. Apply `../supabase/migrations/20261113220000_clinics_and_members.sql` to a dedicated Lala Supabase project when wiring a live DB.
