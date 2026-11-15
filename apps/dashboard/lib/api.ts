import { apiBaseUrl } from "./supabase";
import type {
  ActivityEvent,
  Analytics,
  AppointmentItem,
  AvailabilityWindow,
  CalendarConnection,
  Clinic,
  ClinicService,
  ConsultationItem,
  ConversationDetail,
  ConversationItem,
  CustomerDetail,
  CustomerItem,
  HandoverItem,
  Integration,
  IntegrationActivity,
  IntegrationCreated,
  MeResponse,
  OnboardingState,
  Overview,
  ServiceImportDraft,
  WebsiteKnowledge,
} from "./types";

async function lalaFetch<T>(path: string, accessToken: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "object" && detail?.message
        ? String(detail.message)
        : typeof detail === "string"
          ? detail
          : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return body as T;
}

export function fetchMe(accessToken: string): Promise<MeResponse> {
  return lalaFetch<MeResponse>("/v1/me", accessToken);
}

export function createClinic(
  accessToken: string,
  input: { name: string; timezone?: string },
): Promise<MeResponse> {
  return lalaFetch<MeResponse>("/v1/clinics", accessToken, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function fetchCurrentClinic(accessToken: string): Promise<Clinic> {
  return lalaFetch<Clinic>("/v1/clinics/current", accessToken);
}

export function listIntegrations(accessToken: string): Promise<Integration[]> {
  return lalaFetch<Integration[]>("/v1/integrations", accessToken);
}

export function createIntegration(
  accessToken: string,
  input: { label?: string } = {},
): Promise<IntegrationCreated> {
  return lalaFetch<IntegrationCreated>("/v1/integrations", accessToken, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function revokeIntegration(accessToken: string, integrationId: string): Promise<Integration> {
  return lalaFetch<Integration>(`/v1/integrations/${integrationId}/revoke`, accessToken, {
    method: "POST",
  });
}

export function listIntegrationActivity(accessToken: string): Promise<IntegrationActivity[]> {
  return lalaFetch<IntegrationActivity[]>("/v1/integrations/activity", accessToken);
}

export function fetchOverview(accessToken: string): Promise<Overview> {
  return lalaFetch<Overview>("/v1/overview", accessToken);
}

export function fetchAnalytics(accessToken: string): Promise<Analytics> {
  return lalaFetch<Analytics>("/v1/analytics", accessToken);
}

export function fetchConsultations(accessToken: string): Promise<ConsultationItem[]> {
  return lalaFetch<ConsultationItem[]>("/v1/consultations", accessToken);
}

export function fetchCustomers(accessToken: string): Promise<CustomerItem[]> {
  return lalaFetch<CustomerItem[]>("/v1/customers", accessToken);
}

export function fetchCustomer(accessToken: string, customerId: string): Promise<CustomerDetail> {
  return lalaFetch<CustomerDetail>(`/v1/customers/${customerId}`, accessToken);
}

export function fetchActivity(accessToken: string): Promise<ActivityEvent[]> {
  return lalaFetch<ActivityEvent[]>("/v1/activity", accessToken);
}

export function fetchConversations(accessToken: string): Promise<ConversationItem[]> {
  return lalaFetch<ConversationItem[]>("/v1/conversations", accessToken);
}

export function fetchConversation(
  accessToken: string,
  conversationId: string,
): Promise<ConversationDetail> {
  return lalaFetch<ConversationDetail>(`/v1/conversations/${conversationId}`, accessToken);
}

export function deleteConversation(
  accessToken: string,
  conversationId: string,
): Promise<ConversationDetail> {
  return lalaFetch<ConversationDetail>(`/v1/conversations/${conversationId}`, accessToken, {
    method: "DELETE",
  });
}

export function fetchHandovers(accessToken: string): Promise<HandoverItem[]> {
  return lalaFetch<HandoverItem[]>("/v1/handovers", accessToken);
}

export function updateHandoverStatus(
  accessToken: string,
  handoverId: string,
  status: "open" | "acked" | "closed",
): Promise<HandoverItem> {
  return lalaFetch<HandoverItem>(`/v1/handovers/${handoverId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function fetchServices(accessToken: string): Promise<ClinicService[]> {
  return lalaFetch<ClinicService[]>("/v1/services", accessToken);
}

export function createService(
  accessToken: string,
  input: { name: string; category: string; duration_minutes: number; price_paise?: number },
): Promise<ClinicService> {
  return lalaFetch<ClinicService>("/v1/services", accessToken, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function fetchAvailability(accessToken: string): Promise<AvailabilityWindow[]> {
  return lalaFetch<AvailabilityWindow[]>("/v1/availability", accessToken);
}

export function createAvailability(
  accessToken: string,
  input: { weekday: number; start_minute: number; end_minute: number },
): Promise<AvailabilityWindow> {
  return lalaFetch<AvailabilityWindow>("/v1/availability", accessToken, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function fetchAppointments(accessToken: string): Promise<AppointmentItem[]> {
  return lalaFetch<AppointmentItem[]>("/v1/appointments", accessToken);
}

export function createAppointment(
  accessToken: string,
  input: { customer_id: string; service_id: string; starts_at_utc: string },
): Promise<AppointmentItem> {
  return lalaFetch<AppointmentItem>("/v1/appointments", accessToken, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function cancelAppointment(
  accessToken: string,
  appointmentId: string,
): Promise<AppointmentItem> {
  return lalaFetch<AppointmentItem>(`/v1/appointments/${appointmentId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify({ status: "cancelled" }),
  });
}

export function rescheduleAppointment(
  accessToken: string,
  appointmentId: string,
  input: { starts_at_utc: string },
): Promise<AppointmentItem> {
  return lalaFetch<AppointmentItem>(`/v1/appointments/${appointmentId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function fetchOnboarding(accessToken: string): Promise<OnboardingState> {
  return lalaFetch<OnboardingState>("/v1/onboarding", accessToken);
}

export function updateOnboardingClinic(
  accessToken: string,
  input: { name: string; timezone: string },
): Promise<OnboardingState> {
  return lalaFetch<OnboardingState>("/v1/onboarding/clinic", accessToken, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function skipOnboardingStep(accessToken: string, step: string): Promise<OnboardingState> {
  return lalaFetch<OnboardingState>(`/v1/onboarding/steps/${step}/skip`, accessToken, {
    method: "POST",
  });
}

export function fetchWebsiteKnowledge(accessToken: string): Promise<WebsiteKnowledge> {
  return lalaFetch<WebsiteKnowledge>("/v1/website/knowledge", accessToken);
}

export function startWebsiteImport(
  accessToken: string,
  input: { url: string },
): Promise<{ drafts_created: number; pages_fetched: number; website_url: string }> {
  return lalaFetch("/v1/website/import", accessToken, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function fetchImportDrafts(accessToken: string): Promise<ServiceImportDraft[]> {
  return lalaFetch<ServiceImportDraft[]>("/v1/website/drafts", accessToken);
}

export function reviewImportDraft(
  accessToken: string,
  draftId: string,
  input: { action: "approve" | "reject" | "merge"; merge_into_service_id?: string; edits?: Record<string, unknown> },
): Promise<ServiceImportDraft> {
  return lalaFetch<ServiceImportDraft>(`/v1/website/drafts/${draftId}/review`, accessToken, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function fetchCalendarConnection(accessToken: string): Promise<CalendarConnection> {
  return lalaFetch<CalendarConnection>("/v1/calendar/connection", accessToken);
}

export function setSchedulingMode(
  accessToken: string,
  mode: "lala_only" | "google" | "calcom",
): Promise<CalendarConnection> {
  return lalaFetch<CalendarConnection>("/v1/calendar/scheduling-mode", accessToken, {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export function startGoogleCalendarOAuth(
  accessToken: string,
): Promise<{ authorize_url: string | null; message?: string }> {
  return lalaFetch("/v1/calendar/google/authorize", accessToken, { method: "POST" });
}

export function connectCalcom(
  accessToken: string,
  apiKey: string,
): Promise<CalendarConnection> {
  return lalaFetch<CalendarConnection>("/v1/calendar/calcom/connect", accessToken, {
    method: "POST",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export function disconnectCalcom(accessToken: string): Promise<CalendarConnection> {
  return lalaFetch<CalendarConnection>("/v1/calendar/calcom/disconnect", accessToken, {
    method: "POST",
  });
}

export function disconnectGoogleCalendar(accessToken: string): Promise<CalendarConnection> {
  return lalaFetch<CalendarConnection>("/v1/calendar/google/disconnect", accessToken, {
    method: "POST",
  });
}
