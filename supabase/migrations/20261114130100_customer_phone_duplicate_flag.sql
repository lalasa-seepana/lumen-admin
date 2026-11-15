-- Epic 3: flag possible phone duplicates without auto-merging customers.

alter table public.customers
  add column if not exists possible_phone_duplicate boolean not null default false;
