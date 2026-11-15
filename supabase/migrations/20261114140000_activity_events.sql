-- Epic 4: clinic-scoped activity history (no secrets).

create table if not exists public.activity_events (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  actor_type text not null check (actor_type in ('system', 'owner', 'integration')),
  action text not null,
  entity_type text not null,
  entity_id uuid,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists activity_events_clinic_created_idx
  on public.activity_events (clinic_id, created_at desc);

alter table public.activity_events enable row level security;
revoke all on table public.activity_events from public, anon;
grant select on table public.activity_events to authenticated;

drop policy if exists activity_events_select_member on public.activity_events;
create policy activity_events_select_member
  on public.activity_events
  for select
  to authenticated
  using (
    clinic_id in (
      select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid()
    )
  );

revoke insert, update, delete on table public.activity_events from anon, authenticated;
