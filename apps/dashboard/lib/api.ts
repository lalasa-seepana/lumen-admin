import { apiBaseUrl } from "./supabase";
import type { Clinic, MeResponse } from "./types";

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
