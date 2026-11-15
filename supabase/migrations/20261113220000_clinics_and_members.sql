-- Clinic Dial clinic tenancy. Additive. Separate Supabase project from Lumen.
-- Owners sign up via Supabase Auth; membership is the isolation boundary.

create extension if not exists "pgcrypto";

create table if not exists public.clinics (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(btrim(name)) between 2 and 120),
  timezone text not null default 'Asia/Kolkata',
  created_at timestamptz not null default now()
);

create table if not exists public.clinic_members (
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null check (role in ('owner')),
  created_at timestamptz not null default now(),
  primary key (clinic_id, user_id)
);

create unique index if not exists clinic_members_one_owner_clinic_idx
  on public.clinic_members (user_id)
  where role = 'owner';

create index if not exists clinic_members_user_id_idx on public.clinic_members (user_id);

alter table public.clinics enable row level security;
alter table public.clinic_members enable row level security;

revoke all on table public.clinics from public, anon;
revoke all on table public.clinic_members from public, anon;

grant select on table public.clinics to authenticated;
grant select on table public.clinic_members to authenticated;

drop policy if exists clinics_select_member on public.clinics;
create policy clinics_select_member
  on public.clinics
  for select
  to authenticated
  using (
    id in (
      select cm.clinic_id
      from public.clinic_members cm
      where cm.user_id = auth.uid()
    )
  );

drop policy if exists clinic_members_select_own on public.clinic_members;
create policy clinic_members_select_own
  on public.clinic_members
  for select
  to authenticated
  using (user_id = auth.uid());

-- Mutations go through FastAPI (service role). No insert/update/delete for anon/authenticated.
revoke insert, update, delete on table public.clinics from anon, authenticated;
revoke insert, update, delete on table public.clinic_members from anon, authenticated;
