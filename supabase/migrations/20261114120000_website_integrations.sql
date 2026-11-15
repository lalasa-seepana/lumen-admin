-- Epic 2: per-clinic website integration keys + activity.
-- Additive. Mutations go through FastAPI (service role). Separate Clinic Dial Supabase project.

create table if not exists public.website_integrations (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  key_hash text not null,
  key_prefix text not null check (char_length(key_prefix) between 6 and 16),
  label text not null default 'Website',
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  constraint website_integrations_key_hash_unique unique (key_hash)
);

create index if not exists website_integrations_clinic_id_idx
  on public.website_integrations (clinic_id);

create table if not exists public.customers (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  email_normalized text not null,
  full_name text not null,
  phone_e164 text,
  created_at timestamptz not null default now(),
  constraint customers_clinic_email_unique unique (clinic_id, email_normalized)
);

create index if not exists customers_clinic_id_idx on public.customers (clinic_id);

create table if not exists public.consultations (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  customer_id uuid not null references public.customers (id) on delete restrict,
  category text not null,
  service_external_id text,
  service_name text,
  external_enquiry_id text not null,
  consent_ai_call boolean not null,
  consent_text text not null,
  consent_version text not null,
  consented_at timestamptz not null,
  source_website text not null,
  source_submitted_at timestamptz not null,
  idempotency_key text not null,
  created_at timestamptz not null default now(),
  constraint consultations_clinic_idempotency_unique unique (clinic_id, idempotency_key)
);

create index if not exists consultations_clinic_id_idx on public.consultations (clinic_id);
create index if not exists consultations_customer_id_idx on public.consultations (customer_id);

create table if not exists public.integration_activity (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  integration_id uuid references public.website_integrations (id) on delete set null,
  status text not null check (status in ('accepted', 'duplicate', 'rejected')),
  reason text,
  idempotency_key text,
  created_at timestamptz not null default now()
);

create index if not exists integration_activity_clinic_created_idx
  on public.integration_activity (clinic_id, created_at desc);

alter table public.website_integrations enable row level security;
alter table public.customers enable row level security;
alter table public.consultations enable row level security;
alter table public.integration_activity enable row level security;

revoke all on table public.website_integrations from public, anon;
revoke all on table public.customers from public, anon;
revoke all on table public.consultations from public, anon;
revoke all on table public.integration_activity from public, anon;

grant select on table public.website_integrations to authenticated;
grant select on table public.customers to authenticated;
grant select on table public.consultations to authenticated;
grant select on table public.integration_activity to authenticated;

drop policy if exists website_integrations_select_member on public.website_integrations;
create policy website_integrations_select_member
  on public.website_integrations
  for select
  to authenticated
  using (
    clinic_id in (
      select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid()
    )
  );

drop policy if exists customers_select_member on public.customers;
create policy customers_select_member
  on public.customers
  for select
  to authenticated
  using (
    clinic_id in (
      select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid()
    )
  );

drop policy if exists consultations_select_member on public.consultations;
create policy consultations_select_member
  on public.consultations
  for select
  to authenticated
  using (
    clinic_id in (
      select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid()
    )
  );

drop policy if exists integration_activity_select_member on public.integration_activity;
create policy integration_activity_select_member
  on public.integration_activity
  for select
  to authenticated
  using (
    clinic_id in (
      select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid()
    )
  );

revoke insert, update, delete on table public.website_integrations from anon, authenticated;
revoke insert, update, delete on table public.customers from anon, authenticated;
revoke insert, update, delete on table public.consultations from anon, authenticated;
revoke insert, update, delete on table public.integration_activity from anon, authenticated;
