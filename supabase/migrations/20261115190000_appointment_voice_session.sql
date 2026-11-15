-- Link appointments created via receptionist voice tools to the voice session
-- so conversation detail can surface booked calendar slots.

alter table public.appointments
  add column if not exists voice_session_id uuid references public.voice_sessions (id) on delete set null;

create index if not exists appointments_voice_session_id_idx
  on public.appointments (voice_session_id)
  where voice_session_id is not null;
