-- Stages 2–5: SaaS extensions — onboarding, website import drafts, public slug,
-- Google Calendar fields, visitor voice sessions.

alter table public.clinics
  add column if not exists public_slug text,
  add column if not exists website_url text,
  add column if not exists website_last_error text,
  add column if not exists scheduling_mode text not null default 'unset'
    check (scheduling_mode in ('unset', 'lala_only', 'google')),
  add column if not exists google_refresh_token_enc text,
  add column if not exists google_calendar_id text,
  add column if not exists google_last_sync_at timestamptz,
  add column if not exists google_last_error text,
  add column if not exists google_status text not null default 'disconnected'
    check (google_status in ('connected', 'disconnected', 'error', 'syncing'));

create unique index if not exists clinics_public_slug_idx
  on public.clinics (public_slug)
  where public_slug is not null;

alter table public.clinic_services
  add column if not exists source_url text,
  add column if not exists imported_at timestamptz;

create table if not exists public.service_import_drafts (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  name text,
  description text,
  duration_minutes integer,
  price_paise integer,
  currency text,
  category text,
  source_url text,
  imported_at timestamptz not null default now(),
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'merged'))
);

create index if not exists service_import_drafts_clinic_idx
  on public.service_import_drafts (clinic_id, imported_at desc);

create table if not exists public.website_pages (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  url text not null,
  title text not null,
  body_excerpt text not null default '',
  fetched_at timestamptz not null default now()
);

create index if not exists website_pages_clinic_idx
  on public.website_pages (clinic_id, fetched_at desc);

create table if not exists public.onboarding_steps (
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  step_key text not null,
  status text not null check (status in ('completed', 'incomplete', 'failed', 'skipped')),
  detail text,
  error text,
  updated_at timestamptz,
  primary key (clinic_id, step_key)
);

alter table public.voice_sessions
  add column if not exists visitor_token text,
  add column if not exists actor_type text not null default 'owner'
    check (actor_type in ('owner', 'visitor'));

create unique index if not exists voice_sessions_visitor_token_idx
  on public.voice_sessions (visitor_token)
  where visitor_token is not null;

-- Optional: map Clinic Dial appointments to Google events (Stage 4).
create table if not exists public.calendar_external_mappings (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  appointment_id uuid not null references public.appointments (id) on delete cascade,
  provider text not null default 'google',
  external_event_id text not null,
  created_at timestamptz not null default now(),
  unique (appointment_id, provider)
);

create index if not exists calendar_external_mappings_clinic_idx
  on public.calendar_external_mappings (clinic_id);