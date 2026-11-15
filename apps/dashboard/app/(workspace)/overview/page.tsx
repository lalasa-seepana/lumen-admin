"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import {
  fetchAppointments,
  fetchConsultations,
  fetchHandovers,
  fetchOverview,
} from "@/lib/api";
import type { AppointmentItem, ConsultationItem, HandoverItem, Overview } from "@/lib/types";

export default function OverviewPage() {
  const { accessToken } = useAuth();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [enquiries, setEnquiries] = useState<ConsultationItem[]>([]);
  const [handovers, setHandovers] = useState<HandoverItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const [ov, appts, cons, hand] = await Promise.all([
        fetchOverview(accessToken),
        fetchAppointments(accessToken),
        fetchConsultations(accessToken),
        fetchHandovers(accessToken),
      ]);
      setOverview(ov);
      setAppointments(appts.filter((a) => a.status !== "cancelled"));
      setEnquiries(cons);
      setHandovers(hand.filter((h) => h.status === "open"));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not load your overview. Refresh to try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const upcoming = appointments
    .filter((a) => new Date(a.starts_at_utc).getTime() >= Date.now() - 60_000)
    .sort((a, b) => a.starts_at_utc.localeCompare(b.starts_at_utc))
    .slice(0, 5);

  const actions = [
    {
      href: "/services",
      label: "Review services",
      done: null as boolean | null,
      hint: "Add or approve services visitors can book.",
    },
    {
      href: "/integrations",
      label: "Connect website enquiries",
      done:
        overview == null ? null : overview.integrations_active_count > 0,
      hint:
        overview == null
          ? "Checking enquiry connection…"
          : overview.integrations_active_count > 0
            ? `${overview.integrations_active_count} active enquiry key${overview.integrations_active_count === 1 ? "" : "s"}`
            : "No active enquiry key yet.",
    },
    {
      href: "/calendar",
      label: "Set opening hours",
      done: loading ? null : appointments.length > 0,
      hint: loading
        ? "Checking appointments…"
        : appointments.length > 0
          ? `${appointments.length} active appointment${appointments.length === 1 ? "" : "s"}`
          : "No appointments yet. Set hours, then create one.",
    },
    {
      href: "/onboarding",
      label: "Continue setup checklist",
      done: null,
      hint: "See which setup steps are still open.",
    },
  ];

  return (
    <>
      <PageHeader
        title="Overview"
        description="What needs attention in your clinic today."
        actions={
          <button type="button" className="secondary" onClick={() => void refresh()}>
            Refresh
          </button>
        }
      />
      <div className="page-body">
        {error ? <p className="error">{error}</p> : null}

        {loading && !overview ? (
          <p className="meta">Loading overview…</p>
        ) : overview ? (
          <ul className="stat-grid">
            <li>
              <strong>{upcoming.length}</strong>
              <span>Upcoming shown</span>
            </li>
            <li>
              <strong>{enquiries.length}</strong>
              <span>Enquiries</span>
            </li>
            <li>
              <strong>{handovers.length}</strong>
              <span>Open handovers</span>
            </li>
            <li>
              <strong>{overview.integrations_active_count}</strong>
              <span>Enquiry keys</span>
            </li>
          </ul>
        ) : null}

        <section className="panel stack">
          <h2 className="panel-title">Upcoming appointments</h2>
          {loading ? (
            <p className="meta">Loading appointments…</p>
          ) : upcoming.length === 0 ? (
            <div className="empty-state">
              <strong>No upcoming appointments</strong>
              Set opening hours, then create an appointment from Calendar.
            </div>
          ) : (
            <ul className="data-list">
              {upcoming.map((row) => (
                <li key={row.id}>
                  <strong>
                    {row.starts_at_clinic} · {row.service_name}
                  </strong>
                  <p className="meta">
                    {row.customer_name} · {row.status}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <Link href="/calendar" className="btn secondary" style={{ display: "inline-block", textAlign: "center" }}>
            Open calendar
          </Link>
        </section>

        <section className="panel stack">
          <h2 className="panel-title">New enquiries</h2>
          {loading ? (
            <p className="meta">Loading enquiries…</p>
          ) : enquiries.length === 0 ? (
            <div className="empty-state">
              <strong>No enquiries yet</strong>
              Create an enquiry key under Integrations, then connect your website form.
            </div>
          ) : (
            <ul className="data-list">
              {enquiries.slice(0, 5).map((row) => (
                <li key={row.id}>
                  <strong>{row.customer_name}</strong>
                  <p className="meta">
                    {row.category}
                    {row.service_name ? ` · ${row.service_name}` : ""} · {row.source_website}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel stack">
          <h2 className="panel-title">Open handovers</h2>
          {loading ? (
            <p className="meta">Loading handovers…</p>
          ) : handovers.length === 0 ? (
            <div className="empty-state">
              <strong>No open handovers</strong>
              When a visitor asks for a person, the request appears here.
            </div>
          ) : (
            <ul className="data-list">
              {handovers.slice(0, 5).map((row) => (
                <li key={row.id}>
                  <strong>{row.reason}</strong>
                  <p className="meta">{row.summary}</p>
                </li>
              ))}
            </ul>
          )}
          <Link href="/handovers" className="btn secondary" style={{ display: "inline-block", textAlign: "center" }}>
            Open handovers
          </Link>
        </section>

        <section className="panel stack">
          <h2 className="panel-title">Next steps</h2>
          <ul className="data-list">
            {actions.map((action) => (
              <li key={action.href}>
                <Link href={action.href} className="text-link">
                  {action.label}
                </Link>
                <p className="meta">
                  {action.done === true ? "Done. " : action.done === false ? "Still open. " : ""}
                  {action.hint}
                </p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
