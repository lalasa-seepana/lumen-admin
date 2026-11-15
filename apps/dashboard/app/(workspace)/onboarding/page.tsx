"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import {
  fetchOnboarding,
  setSchedulingMode,
  skipOnboardingStep,
  startWebsiteImport,
  updateOnboardingClinic,
  createAvailability,
} from "@/lib/api";
import type { OnboardingState } from "@/lib/types";

const STEP_META: Record<string, { title: string; href?: string }> = {
  clinic_profile: { title: "Clinic name and timezone" },
  website_url: { title: "Website URL" },
  discover_review: { title: "Review imported services", href: "/services" },
  calendar_choice: { title: "Choose calendar setup", href: "/integrations" },
  opening_hours: { title: "Set opening hours", href: "/calendar" },
  receptionist: { title: "Configure the receptionist", href: "/receptionist" },
};

export default function OnboardingPage() {
  const { accessToken, refreshMe } = useAuth();
  const [state, setState] = useState<OnboardingState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [startTime, setStartTime] = useState("10:00");
  const [endTime, setEndTime] = useState("18:00");

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      const row = await fetchOnboarding(accessToken);
      setState(row);
      setName(row.clinic_name);
      setTimezone(row.timezone);
      setWebsiteUrl(row.website_url ?? "");
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not load setup progress. Refresh to try again.",
      );
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSaveClinic(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setBusy(true);
    try {
      setState(await updateOnboardingClinic(accessToken, { name, timezone }));
      await refreshMe();
      setNotice("Clinic profile saved.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not save your clinic profile. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onWebsite(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setBusy(true);
    try {
      await startWebsiteImport(accessToken, { url: websiteUrl });
      await refresh();
      setNotice("Website import finished. Review draft services next.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Import failed. Check the URL and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onLalaOnly() {
    if (!accessToken) return;
    setBusy(true);
    try {
      await setSchedulingMode(accessToken, "lala_only");
      await refresh();
      setNotice("Clinic Dial-only scheduling selected.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not save that choice. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onHours(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setBusy(true);
    try {
      const [sh, sm] = startTime.split(":").map(Number);
      const [eh, em] = endTime.split(":").map(Number);
      for (let weekday = 0; weekday < 5; weekday++) {
        await createAvailability(accessToken, {
          weekday,
          start_minute: sh * 60 + sm,
          end_minute: eh * 60 + em,
        });
      }
      await refresh();
      setNotice("Monday to Friday opening hours saved.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not save opening hours. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onSkip(step: string) {
    if (!accessToken) return;
    setBusy(true);
    try {
      setState(await skipOnboardingStep(accessToken, step));
      setNotice("Step skipped. You can return to it anytime.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not skip that step. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Setup"
        description="Finish these steps at your own pace. Each step shows whether it is complete, open, failed, or skipped."
      />
      <div className="page-body">
        {error ? <p className="error">{error}</p> : null}
        {notice ? <p className="notice">{notice}</p> : null}

        {!state ? (
          <p className="meta">Loading setup…</p>
        ) : (
          <ol className="onboarding-steps">
            {state.steps.map((step, index) => {
              const meta = STEP_META[step.key] ?? { title: step.key };
              return (
                <li key={step.key}>
                  <span className="step-num">{index + 1}</span>
                  <div>
                    <strong>{meta.title}</strong>
                    <p className="meta">{step.detail || step.error || "No notes yet"}</p>
                    {step.key === "clinic_profile" && step.status !== "completed" ? (
                      <form className="stack" style={{ marginTop: "0.75rem" }} onSubmit={onSaveClinic}>
                        <label>
                          Clinic name
                          <input required value={name} onChange={(e) => setName(e.target.value)} />
                        </label>
                        <label>
                          Timezone
                          <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                            <option value="Asia/Kolkata">Asia/Kolkata</option>
                            <option value="Asia/Bangkok">Asia/Bangkok</option>
                            <option value="Asia/Dubai">Asia/Dubai</option>
                            <option value="Europe/London">Europe/London</option>
                            <option value="America/New_York">America/New_York</option>
                          </select>
                        </label>
                        <button type="submit" disabled={busy}>
                          Save clinic profile
                        </button>
                      </form>
                    ) : null}
                    {step.key === "website_url" && step.status !== "completed" ? (
                      <form className="stack" style={{ marginTop: "0.75rem" }} onSubmit={onWebsite}>
                        <label>
                          Website URL
                          <input
                            type="url"
                            required
                            value={websiteUrl}
                            onChange={(e) => setWebsiteUrl(e.target.value)}
                          />
                        </label>
                        <button type="submit" disabled={busy}>
                          Save and import
                        </button>
                      </form>
                    ) : null}
                    {step.key === "calendar_choice" && step.status !== "completed" ? (
                      <div className="row" style={{ marginTop: "0.75rem" }}>
                        <button type="button" className="secondary" disabled={busy} onClick={() => void onLalaOnly()}>
                          Use Clinic Dial-only scheduling
                        </button>
                        <Link href="/integrations" className="btn">
                          Connect Google or Cal.com
                        </Link>
                      </div>
                    ) : null}
                    {step.key === "opening_hours" && step.status !== "completed" ? (
                      <form className="stack" style={{ marginTop: "0.75rem" }} onSubmit={onHours}>
                        <label>
                          Weekdays open
                          <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
                        </label>
                        <label>
                          Weekdays close
                          <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
                        </label>
                        <button type="submit" disabled={busy}>
                          Save Mon–Fri hours
                        </button>
                      </form>
                    ) : null}
                    {step.key === "receptionist" ? (
                      <div className="row" style={{ marginTop: "0.75rem" }}>
                        <Link href="/receptionist" className="btn">
                          Open receptionist settings
                        </Link>
                      </div>
                    ) : null}
                    {meta.href && step.status === "completed" ? (
                      <p className="meta">
                        <Link href={meta.href}>Open related page</Link>
                      </p>
                    ) : null}
                  </div>
                  <div className="stack" style={{ justifyItems: "end" }}>
                    <span
                      className={`status-pill status-${
                        step.status === "failed"
                          ? "failed"
                          : step.status === "completed"
                            ? "accepted"
                            : "duplicate"
                      }`}
                    >
                      {step.status}
                    </span>
                    {step.status !== "completed" && step.status !== "skipped" ? (
                      <button type="button" className="ghost" disabled={busy} onClick={() => void onSkip(step.key)}>
                        Skip for now
                      </button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </>
  );
}
