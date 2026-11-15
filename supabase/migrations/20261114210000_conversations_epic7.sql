-- Epic 7: conversations, transcript turns, retention metadata.
-- Additive. Handovers already exist from Epic 6; link conversation_id when present.

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  voice_session_id uuid not null references public.voice_sessions (id) on delete cascade,
  language text not null check (language in ('en-IN', 'hi-IN', 'te-IN')),
  recording_consent boolean not null default false,
  retention_until timestamptz not null,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  closed_at timestamptz,
  unique (voice_session_id)
);

create index if not exists conversations_clinic_created_idx
  on public.conversations (clinic_id, created_at desc);

create table if not exists public.conversation_turns (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations (id) on delete cascade,
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  sequence integer not null check (sequence >= 0),
  role text not null check (role in ('user', 'assistant', 'system')),
  text text not null,
  -- Audio blobs are never stored without recording_consent; key is optional metadata only.
  has_audio_blob boolean not null default false,
  audio_storage_key text,
  created_at timestamptz not null default now(),
  unique (conversation_id, sequence)
);

create index if not exists conversation_turns_conversation_idx
  on public.conversation_turns (conversation_id, sequence);

alter table public.handovers
  add column if not exists conversation_id uuid references public.conversations (id) on delete set null;

alter table public.conversations enable row level security;
alter table public.conversation_turns enable row level security;

revoke all on table public.conversations from public, anon;
revoke all on table public.conversation_turns from public, anon;

grant select on table public.conversations to authenticated;
grant select on table public.conversation_turns to authenticated;

drop policy if exists conversations_select_member on public.conversations;
create policy conversations_select_member on public.conversations
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
    and deleted_at is null
  );

drop policy if exists conversation_turns_select_member on public.conversation_turns;
create policy conversation_turns_select_member on public.conversation_turns
  for select to authenticated using (
    clinic_id in (select cm.clinic_id from public.clinic_members cm where cm.user_id = auth.uid())
    and conversation_id in (
      select c.id from public.conversations c
      where c.deleted_at is null and c.recording_consent = true
    )
  );

revoke insert, update, delete on table public.conversations from anon, authenticated;
revoke insert, update, delete on table public.conversation_turns from anon, authenticated;
