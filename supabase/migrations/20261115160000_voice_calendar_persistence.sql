-- Voice + calendar persistence: appointment sync fields, OAuth state, Cal.com,
-- external busy blocks, overlap prevention.

create extension if not exists btree_gist;

-- Appointments: provider sync + idempotency
alter table public.appointments
  add column if not exists idempotency_key text,
  add column if not exists provider text not null default 'lala',
  add column if not exists sync_status text not null default 'local',
  add column if not exists external_event_id text;

alter table public.appointments drop constraint if exists appointments_status_check;
alter table public.appointments
  add constraint appointments_status_check
    check (status in ('booked', 'rescheduled', 'cancelled', 'pending'));

create unique index if not exists appointments_clinic_idempotency_idx
  on public.appointments (clinic_id, idempotency_key)
  where idempotency_key is not null;

alter table public.appointments drop constraint if exists appointments_no_overlap;
alter table public.appointments
  add constraint appointments_no_overlap
  exclude using gist (
    clinic_id with =,
    tstzrange(starts_at_utc, ends_at_utc, '[)') with &&
  ) where (status <> 'cancelled');

-- Voice session verification / booking-in-progress fields
alter table public.voice_sessions
  add column if not exists customer_id uuid references public.customers (id) on delete set null,
  add column if not exists customer_verified_at timestamptz,
  add column if not exists pending_email text,
  add column if not exists pending_phone text,
  add column if not exists pending_full_name text,
  add column if not exists verification_code_hash text,
  add column if not exists verification_expires_at timestamptz,
  add column if not exists verification_attempts integer not null default 0,
  add column if not exists selected_service_id uuid references public.clinic_services (id) on delete set null,
  add column if not exists selected_starts_at_utc timestamptz,
  add column if not exists callback_contact text,
  add column if not exists consent_version text,
  add column if not exists consent_recorded_at timestamptz;

alter table public.handovers
  add column if not exists callback_contact text;

-- OAuth CSRF state (Google, etc.)
create table if not exists public.oauth_states (
  state text primary key,
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  user_id uuid not null,
  provider text not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists oauth_states_expires_idx on public.oauth_states (expires_at);

-- Per-clinic external calendar connections (Cal.com; Google fields remain on clinics)
create table if not exists public.calendar_connections (
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  provider text not null check (provider in ('google', 'calcom')),
  api_key_enc text,
  status text not null default 'disconnected'
    check (status in ('connected', 'disconnected', 'error', 'syncing')),
  last_sync_at timestamptz,
  last_error text,
  config jsonb not null default '{}'::jsonb,
  webhook_secret text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (clinic_id, provider)
);

-- scheduling_mode may include Cal.com
alter table public.clinics drop constraint if exists clinics_scheduling_mode_check;
alter table public.clinics
  add constraint clinics_scheduling_mode_check
    check (scheduling_mode in ('unset', 'lala_only', 'google', 'calcom'));

-- Imported personal/busy blocks (do not create customers)
create table if not exists public.calendar_busy_blocks (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  provider text not null,
  external_id text not null,
  starts_at_utc timestamptz not null,
  ends_at_utc timestamptz not null,
  summary text,
  created_at timestamptz not null default now(),
  unique (clinic_id, provider, external_id),
  check (ends_at_utc > starts_at_utc)
);

create index if not exists calendar_busy_blocks_clinic_starts_idx
  on public.calendar_busy_blocks (clinic_id, starts_at_utc);

-- RLS
alter table public.oauth_states enable row level security;
alter table public.calendar_connections enable row level security;
alter table public.calendar_busy_blocks enable row level security;

revoke all on table public.oauth_states from public, anon;
revoke all on table public.calendar_connections from public, anon;
revoke all on table public.calendar_busy_blocks from public, anon;

grant select on table public.oauth_states to authenticated;
grant select on table public.calendar_connections to authenticated;
grant select on table public.calendar_busy_blocks to authenticated;

drop policy if exists oauth_states_select_member on public.oauth_states;
create policy oauth_states_select_member on public.oauth_states
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

drop policy if exists calendar_connections_select_member on public.calendar_connections;
create policy calendar_connections_select_member on public.calendar_connections
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

drop policy if exists calendar_busy_blocks_select_member on public.calendar_busy_blocks;
create policy calendar_busy_blocks_select_member on public.calendar_busy_blocks
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

revoke insert, update, delete on table public.oauth_states from anon, authenticated;
revoke insert, update, delete on table public.calendar_connections from anon, authenticated;
revoke insert, update, delete on table public.calendar_busy_blocks from anon, authenticated;