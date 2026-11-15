-- Epic 6 (+ minimal Epic 5 surface for voice tools): services, availability,
-- appointments, voice sessions, handovers. Additive. Separate Clinic Dial Supabase project.

create table if not exists public.clinic_services (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  name text not null,
  category text not null,
  duration_minutes integer not null check (duration_minutes > 0),
  price_paise integer,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists clinic_services_clinic_id_idx on public.clinic_services (clinic_id);

create table if not exists public.availability_windows (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  weekday smallint not null check (weekday between 0 and 6), -- 0=Monday
  start_minute integer not null check (start_minute between 0 and 1439),
  end_minute integer not null check (end_minute between 1 and 1440),
  check (end_minute > start_minute),
  created_at timestamptz not null default now()
);

create index if not exists availability_windows_clinic_id_idx on public.availability_windows (clinic_id);

create table if not exists public.appointments (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  customer_id uuid not null references public.customers (id) on delete restrict,
  service_id uuid not null references public.clinic_services (id) on delete restrict,
  starts_at_utc timestamptz not null,
  ends_at_utc timestamptz not null,
  status text not null check (status in ('booked', 'rescheduled', 'cancelled')),
  created_at timestamptz not null default now(),
  check (ends_at_utc > starts_at_utc)
);

create index if not exists appointments_clinic_starts_idx
  on public.appointments (clinic_id, starts_at_utc);

create table if not exists public.voice_sessions (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  language text not null check (language in ('en-IN', 'hi-IN', 'te-IN')),
  recording_consent boolean not null default false,
  status text not null default 'open' check (status in ('open', 'closed')),
  created_at timestamptz not null default now(),
  closed_at timestamptz
);

create index if not exists voice_sessions_clinic_id_idx on public.voice_sessions (clinic_id);

create table if not exists public.handovers (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  voice_session_id uuid references public.voice_sessions (id) on delete set null,
  reason text not null,
  summary text not null,
  status text not null default 'open' check (status in ('open', 'acked', 'closed')),
  created_at timestamptz not null default now()
);

create index if not exists handovers_clinic_created_idx
  on public.handovers (clinic_id, created_at desc);

create table if not exists public.tool_audit_events (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  voice_session_id uuid,
  tool_name text not null,
  accepted boolean not null,
  reason text,
  arguments jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists tool_audit_events_clinic_created_idx
  on public.tool_audit_events (clinic_id, created_at desc);

alter table public.clinic_services enable row level security;
alter table public.availability_windows enable row level security;
alter table public.appointments enable row level security;
alter table public.voice_sessions enable row level security;
alter table public.handovers enable row level security;
alter table public.tool_audit_events enable row level security;

revoke all on table public.clinic_services from public, anon;
revoke all on table public.availability_windows from public, anon;
revoke all on table public.appointments from public, anon;
revoke all on table public.voice_sessions from public, anon;
revoke all on table public.handovers from public, anon;
revoke all on table public.tool_audit_events from public, anon;

grant select on table public.clinic_services to authenticated;
grant select on table public.availability_windows to authenticated;
grant select on table public.appointments to authenticated;
grant select on table public.voice_sessions to authenticated;
grant select on table public.handovers to authenticated;
grant select on table public.tool_audit_events to authenticated;

-- Member-scoped select policies
drop policy if exists clinic_services_select_member on public.clinic_services;
create policy clinic_services_select_member on public.clinic_services
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

drop policy if exists availability_windows_select_member on public.availability_windows;
create policy availability_windows_select_member on public.availability_windows
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

drop policy if exists appointments_select_member on public.appointments;
create policy appointments_select_member on public.appointments
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

drop policy if exists voice_sessions_select_member on public.voice_sessions;
create policy voice_sessions_select_member on public.voice_sessions
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

drop policy if exists handovers_select_member on public.handovers;
create policy handovers_select_member on public.handovers
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

drop policy if exists tool_audit_events_select_member on public.tool_audit_events;
create policy tool_audit_events_select_member on public.tool_audit_events
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
  );

revoke insert, update, delete on table public.clinic_services from anon, authenticated;
revoke insert, update, delete on table public.availability_windows from anon, authenticated;
revoke insert, update, delete on table public.appointments from anon, authenticated;
revoke insert, update, delete on table public.voice_sessions from anon, authenticated;
revoke insert, update, delete on table public.handovers from anon, authenticated;
revoke insert, update, delete on table public.tool_audit_events from anon, authenticated;
