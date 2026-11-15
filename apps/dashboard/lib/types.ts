export type Clinic = {
  id: string;
  name: string;
  timezone: string;
  created_at: string;
  public_slug?: string;
};

export type Membership = {
  clinic_id: string;
  user_id: string;
  role: "owner";
};

export type MeResponse = {
  user_id: string;
  email: string | null;
  clinic: Clinic | null;
  membership: Membership | null;
};

export type Integration = {
  id: string;
  clinic_id: string;
  key_prefix: string;
  label: string;
  revoked_at: string | null;
  created_at: string;
};

export type IntegrationCreated = Integration & {
  api_key: string;
};

export type IntegrationActivity = {
  id: string;
  clinic_id: string;
  integration_id: string | null;
  status: "accepted" | "duplicate" | "rejected";
  reason: string | null;
  idempotency_key: string | null;
  created_at: string;
};

export type Overview = {
  clinic_id: string;
  clinic_name: string;
  consultations_count: number;
  customers_count: number;
  integrations_active_count: number;
  activity_count: number;
};

export type Analytics = {
  clinic_id: string;
  clinic_name: string;
  consultations_count: number;
  customers_count: number;
  appointments_count: number;
  open_handovers_count: number;
  conversations_count: number;
  integrations_active_count: number;
  activity_count: number;
  source: string;
};

export type ConsultationItem = {
  id: string;
  clinic_id: string;
  customer_id: string;
  customer_name: string;
  customer_email: string;
  category: string;
  service_name: string | null;
  source_website: string;
  created_at: string;
};

export type CustomerItem = {
  id: string;
  clinic_id: string;
  email_normalized: string;
  full_name: string;
  phone_e164: string | null;
  possible_phone_duplicate: boolean;
  created_at: string;
  consultation_count: number;
};

export type CustomerDetail = CustomerItem & {
  consultations: ConsultationItem[];
};

export type ActivityEvent = {
  id: string;
  clinic_id: string;
  actor_type: "system" | "owner" | "integration";
  action: string;
  entity_type: string;
  entity_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ConversationTurn = {
  id: string;
  sequence: number;
  role: "user" | "assistant" | "system";
  text: string;
  has_audio_blob: boolean;
  created_at: string;
};

export type ConversationItem = {
  id: string;
  clinic_id: string;
  voice_session_id: string;
  language: string;
  recording_consent: boolean;
  transcript_available: boolean;
  retention_until: string;
  deleted_at: string | null;
  turn_count: number;
  handover_count: number;
  appointment_count: number;
  created_at: string;
  closed_at: string | null;
};

export type ConversationDetail = ConversationItem & {
  turns: ConversationTurn[];
  appointments: AppointmentItem[];
  retention_note: string;
};

export type HandoverItem = {
  id: string;
  clinic_id: string;
  voice_session_id: string | null;
  conversation_id: string | null;
  reason: string;
  summary: string;
  status: "open" | "acked" | "closed";
  created_at: string;
};

export type ClinicService = {
  id: string;
  clinic_id: string;
  name: string;
  category: string;
  duration_minutes: number;
  price_paise: number | null;
  active: boolean;
  created_at: string;
  source_url?: string | null;
  imported_at?: string | null;
};

export type ServiceImportDraft = {
  id: string;
  clinic_id: string;
  name: string | null;
  description: string | null;
  duration_minutes: number | null;
  price_paise: number | null;
  currency: string | null;
  category: string | null;
  source_url: string | null;
  imported_at: string;
  status: "pending" | "approved" | "rejected" | "merged";
};

export type WebsiteKnowledge = {
  website_url: string | null;
  last_import_at: string | null;
  last_error: string | null;
  pending_drafts: number;
  pages: { url: string; title: string; fetched_at: string }[];
};

export type CalendarConnection = {
  provider: "google" | "calcom" | null;
  status: "connected" | "disconnected" | "error" | "syncing";
  scheduling_mode: "unset" | "lala_only" | "google" | "calcom";
  last_sync_at: string | null;
  last_error: string | null;
  google_configured: boolean;
  calcom_configured?: boolean;
  google_calendar_id?: string | null;
};

export type OnboardingStep = {
  key: string;
  status: "completed" | "incomplete" | "failed" | "skipped";
  detail: string | null;
  error: string | null;
  updated_at: string | null;
};

export type OnboardingState = {
  clinic_name: string;
  timezone: string;
  website_url: string | null;
  steps: OnboardingStep[];
};

export type AvailabilityWindow = {
  id: string;
  clinic_id: string;
  weekday: number;
  start_minute: number;
  end_minute: number;
  created_at: string;
};

export type AppointmentItem = {
  id: string;
  clinic_id: string;
  customer_id: string;
  customer_name: string;
  service_id: string;
  service_name: string;
  starts_at_utc: string;
  ends_at_utc: string;
  status: string;
  created_at: string;
  starts_at_clinic: string;
  ends_at_clinic: string;
  clinic_timezone: string;
  voice_session_id?: string | null;
  provider?: string;
  sync_status?: string;
  external_event_id?: string | null;
};
