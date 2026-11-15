"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { WebsiteIntegrations } from "@/components/website-integrations";
import { useAuth } from "@/lib/auth-context";
import {
  connectCalcom,
  disconnectCalcom,
  disconnectGoogleCalendar,
  fetchCalendarConnection,
  startGoogleCalendarOAuth,
  setSchedulingMode,
} from "@/lib/api";
import type { CalendarConnection } from "@/lib/types";

export default function IntegrationsPage() {
  const { accessToken, me } = useAuth();
  const [calendar, setCalendar] = useState<CalendarConnection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [calcomKey, setCalcomKey] = useState("");
  const [websiteConnected, setWebsiteConnected] = useState(false);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      setCalendar(await fetchCalendarConnection(accessToken));
      setError(null);
    } catch {
      setCalendar({
        provider: null,
        status: "disconnected",
        scheduling_mode: "unset",
        last_sync_at: null,
        last_error: null,
        google_configured: false,
        calcom_configured: false,
      });
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onLalaOnly() {
    if (!accessToken) return;
    setBusy(true);
    try {
      setCalendar(await setSchedulingMode(accessToken, "lala_only"));
      setNotice("You chose Clinic Dial-only scheduling. Appointments stay in Clinic Dial until you connect Google or Cal.com.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not update scheduling mode. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onGoogle() {
    if (!accessToken) return;
    setBusy(true);
    setError(null);
    try {
      const { authorize_url, message } = await startGoogleCalendarOAuth(accessToken);
      if (authorize_url) {
        window.location.href = authorize_url;
        return;
      }
      setNotice(
        message ??
          "Google Calendar is not configured on this server yet. You can still use Clinic Dial-only scheduling.",
      );
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Google connection could not start. Try again, or use Clinic Dial-only scheduling.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onDisconnectGoogle() {
    if (!accessToken) return;
    setBusy(true);
    setError(null);
    try {
      setCalendar(await disconnectGoogleCalendar(accessToken));
      setNotice("Google Calendar disconnected.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disconnect Google Calendar.");
    } finally {
      setBusy(false);
    }
  }

  async function onCalcomConnect(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !calcomKey.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const connected = await connectCalcom(accessToken, calcomKey.trim());
      setCalendar(await setSchedulingMode(accessToken, "calcom").catch(() => connected));
      setCalcomKey("");
      setNotice(
        "Cal.com connected. New bookings with a customer email appear on Clinic Dial’s calendar and Cal.com; Cal.com emails the customer.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Cal.com rejected this API key. Check the key and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onDisconnectCalcom() {
    if (!accessToken) return;
    setBusy(true);
    setError(null);
    try {
      setCalendar(await disconnectCalcom(accessToken));
      setNotice("Cal.com disconnected.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disconnect Cal.com.");
    } finally {
      setBusy(false);
    }
  }

  const statusLabel =
    calendar?.status === "connected"
      ? "Connected"
      : calendar?.status === "error"
        ? "Needs attention"
        : calendar?.status === "syncing"
          ? "Syncing"
          : "Not connected";

  const modeLabel =
    calendar?.scheduling_mode === "lala_only"
      ? "Clinic Dial only"
      : calendar?.scheduling_mode === "google"
        ? "Google"
        : calendar?.scheduling_mode === "calcom"
          ? "Cal.com"
          : "Not chosen";

  const googleConnected = calendar?.provider === "google" && calendar.status === "connected";
  const calcomConnected = calendar?.provider === "calcom" && calendar.status === "connected";

  return (
    <>
      <PageHeader
        title="Integrations"
        description="Connect enquiry forwarding and calendar providers. Website content import lives under Website."
      />
      <div className="page-body">
        {error ? <p className="error">{error}</p> : null}
        {notice ? <p className="notice">{notice}</p> : null}

        {accessToken ? (
          <WebsiteIntegrations
            accessToken={accessToken}
            clinicName={me?.clinic?.name}
            onConnectionChange={setWebsiteConnected}
          />
        ) : null}

        <section className="panel stack">
          <h2 className="panel-title">Calendar providers</h2>
          {!websiteConnected ? (
            <p className="meta">
              Connect your clinic website under Enquiry forwarding first. Google Calendar and Cal.com stay
              unavailable until that key exists, so calendar sync is always tied to a real website connection.
            </p>
          ) : (
            <>
              <div className="row">
                <span
                  className={`status-pill status-${
                    calendar?.status === "connected"
                      ? "connected"
                      : calendar?.status === "error"
                        ? "failed"
                        : "duplicate"
                  }`}
                >
                  {statusLabel}
                </span>
                <span className="meta">
                  Mode: {modeLabel}
                  {calendar?.last_sync_at
                    ? ` · Last sync ${new Date(calendar.last_sync_at).toLocaleString()}`
                    : ""}
                </span>
              </div>
              {calendar?.last_error ? <p className="error">{calendar.last_error}</p> : null}

              <div className="stack" style={{ gap: "0.75rem" }}>
                <div>
                  <h3 className="panel-subtitle">Google Calendar</h3>
                  <div className="row">
                    {googleConnected ? (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void onDisconnectGoogle()}
                      >
                        Disconnect Google
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={busy || calendar?.google_configured === false}
                        onClick={() => void onGoogle()}
                      >
                        Connect Google Calendar
                      </button>
                    )}
                    <button type="button" className="secondary" disabled={busy} onClick={() => void onLalaOnly()}>
                      Use Clinic Dial-only scheduling
                    </button>
                  </div>
                  {calendar?.google_configured === false ? (
                    <p className="meta">
                      Google OAuth is not set up on this API yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
                      to the Clinic Dial API environment, then restart. Clinic Dial-only scheduling still works for appointments
                      in your clinic.
                    </p>
                  ) : null}
                </div>

                <div>
                  <h3 className="panel-subtitle">Cal.com</h3>
                  {calcomConnected ? (
                    <div className="row">
                      <span className="meta">Connected as the active calendar provider.</span>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void onDisconnectCalcom()}
                      >
                        Disconnect Cal.com
                      </button>
                    </div>
                  ) : (
                    <form className="stack" onSubmit={onCalcomConnect}>
                      <label>
                        Cal.com API key
                        <input
                          type="password"
                          autoComplete="off"
                          placeholder="cal_live_…"
                          value={calcomKey}
                          onChange={(e) => setCalcomKey(e.target.value)}
                          disabled={busy}
                        />
                      </label>
                      <div className="row">
                        <button type="submit" disabled={busy || calcomKey.trim().length < 8}>
                          Connect Cal.com
                        </button>
                      </div>
                      <p className="meta">
                        Paste a Cal.com API key from your Cal.com developer settings. Clinic Dial stores it encrypted and
                        verifies it against Cal.com before marking the connection as live. Bookings for customers
                        with an email are created on Cal.com (so Cal.com sends the confirmation email) and stay on
                        Clinic Dial’s calendar.
                        {calendar?.calcom_configured === false
                          ? " Set CALCOM_WEBHOOK_SECRET on the API so inbound booking webhooks can be verified."
                          : " Webhook verification is configured on this API."}
                      </p>
                    </form>
                  )}
                </div>
              </div>

              <div className="empty-state" style={{ textAlign: "left" }}>
                <strong>Outlook</strong>
                Not available yet. This option will appear here when it is ready to connect.
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
