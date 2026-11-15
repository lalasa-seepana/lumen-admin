"use client";

import { useCallback, useEffect, useState } from "react";
import { AiReceptionistPanel } from "@/components/ai-receptionist-panel";
import { AppointmentsPanel } from "@/components/appointments-panel";
import { WebsiteIntegrations } from "@/components/website-integrations";
import {
  fetchActivity,
  fetchAnalytics,
  fetchConsultations,
  fetchCustomer,
  fetchCustomers,
  fetchOverview,
} from "@/lib/api";
import type {
  ActivityEvent,
  Analytics,
  ConsultationItem,
  CustomerDetail,
  CustomerItem,
  MeResponse,
  Overview,
} from "@/lib/types";

type ModuleId =
  | "overview"
  | "consultations"
  | "customers"
  | "integrations"
  | "activity"
  | "appointments"
  | "ai"
  | "analytics";

const MODULES: { id: ModuleId; label: string; planned?: boolean }[] = [
  { id: "overview", label: "Overview" },
  { id: "consultations", label: "Consultations" },
  { id: "customers", label: "Customers" },
  { id: "integrations", label: "Website integrations" },
  { id: "activity", label: "Activity" },
  { id: "appointments", label: "Appointments" },
  { id: "ai", label: "AI receptionist" },
  { id: "analytics", label: "Analytics" },
];

type Props = {
  accessToken: string;
  me: MeResponse;
  busy: boolean;
  error: string | null;
  notice: string | null;
  onSignOut: () => void;
};

export function OperationsShell({ accessToken, me, busy, error, notice, onSignOut }: Props) {
  const clinic = me.clinic!;
  const [module, setModule] = useState<ModuleId>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerDetail | null>(null);
  const [bookCustomerId, setBookCustomerId] = useState<string | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [ov, cons, cust, act, an] = await Promise.all([
        fetchOverview(accessToken),
        fetchConsultations(accessToken),
        fetchCustomers(accessToken),
        fetchActivity(accessToken),
        fetchAnalytics(accessToken),
      ]);
      setOverview(ov);
      setConsultations(cons);
      setCustomers(cust);
      setActivity(act);
      setAnalytics(an);
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load clinic data");
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function openCustomer(id: string) {
    try {
      const detail = await fetchCustomer(accessToken, id);
      setSelectedCustomer(detail);
      setModule("customers");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load customer");
    }
  }

  return (
    <div className="ops-layout">
      <header className="ops-header">
        <div>
          <p className="ops-brand">Clinic Dial</p>
          <h1 className="ops-clinic">{clinic.name}</h1>
          <p className="meta">
            {me.email ?? me.user_id} · {me.membership?.role ?? "owner"} · {clinic.timezone}
          </p>
        </div>
        <div className="row">
          <button type="button" className="secondary" disabled={busy} onClick={() => void refresh()}>
            Refresh
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </header>

      <nav className="ops-nav" aria-label="Clinic modules">
        {MODULES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={module === item.id ? "ops-nav-active" : undefined}
            aria-current={module === item.id ? "page" : undefined}
            onClick={() => {
              setModule(item.id);
              if (item.id !== "customers") setSelectedCustomer(null);
            }}
          >
            {item.label}
            {item.planned ? <span className="planned-tag">Planned</span> : null}
          </button>
        ))}
      </nav>

      <main className="ops-main">
        {notice ? (
          <p className="notice" role="status" aria-live="polite">
            {notice}
          </p>
        ) : null}
        {error || loadError ? (
          <p className="error" role="alert" aria-live="assertive">
            {error ?? loadError}
          </p>
        ) : null}

        {module === "overview" ? (
          <section className="panel stack" aria-labelledby="overview-title">
            <h2 id="overview-title" className="panel-title">
              Overview
            </h2>
            <p className="panel-hint">Counts from your clinic records only.</p>
            {overview ? (
              <ul className="count-grid">
                <li>
                  <strong>{overview.consultations_count}</strong>
                  <span>Consultations</span>
                </li>
                <li>
                  <strong>{overview.customers_count}</strong>
                  <span>Customers</span>
                </li>
                <li>
                  <strong>{overview.integrations_active_count}</strong>
                  <span>Active keys</span>
                </li>
                <li>
                  <strong>{overview.activity_count}</strong>
                  <span>Activity events</span>
                </li>
              </ul>
            ) : (
              <p className="meta">Loading counts…</p>
            )}
          </section>
        ) : null}

        {module === "consultations" ? (
          <section className="panel stack" aria-labelledby="consultations-title">
            <h2 id="consultations-title" className="panel-title">
              Consultations
            </h2>
            <p className="panel-hint">Website enquiries forwarded into this clinic.</p>
            {consultations.length === 0 ? (
              <p className="meta">No enquiries yet. Connect a website key and submit a DEMO- form.</p>
            ) : (
              <ul className="data-list">
                {consultations.map((row) => (
                  <li key={row.id}>
                    <button type="button" className="text-link" onClick={() => void openCustomer(row.customer_id)}>
                      {row.customer_name}
                    </button>
                    <p className="meta">
                      {row.category}
                      {row.service_name ? ` · ${row.service_name}` : ""} · {row.source_website}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}

        {module === "customers" ? (
          <section className="panel stack" aria-labelledby="customers-title">
            <h2 id="customers-title" className="panel-title">
              Customers
            </h2>
            {selectedCustomer ? (
              <div className="stack">
                <button type="button" className="text-link" onClick={() => setSelectedCustomer(null)}>
                  ← All customers
                </button>
                <h3 className="panel-subtitle">{selectedCustomer.full_name}</h3>
                <p className="meta">
                  {selectedCustomer.email_normalized}
                  {selectedCustomer.phone_e164 ? ` · ${selectedCustomer.phone_e164}` : ""}
                  {selectedCustomer.possible_phone_duplicate ? " · possible phone duplicate" : ""}
                </p>
                <ul className="data-list">
                  {selectedCustomer.consultations.map((row) => (
                    <li key={row.id}>
                      <strong>{row.category}</strong>
                      <p className="meta">{row.service_name ?? "Service"} · {row.created_at}</p>
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => {
                    setBookCustomerId(selectedCustomer.id);
                    setModule("appointments");
                  }}
                >
                  Book appointment
                </button>
              </div>
            ) : customers.length === 0 ? (
              <p className="meta">No customers yet.</p>
            ) : (
              <ul className="data-list">
                {customers.map((row) => (
                  <li key={row.id}>
                    <button type="button" className="text-link" onClick={() => void openCustomer(row.id)}>
                      {row.full_name}
                    </button>
                    <p className="meta">
                      {row.email_normalized} · {row.consultation_count} consultation
                      {row.consultation_count === 1 ? "" : "s"}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}

        {module === "integrations" ? <WebsiteIntegrations accessToken={accessToken} /> : null}

        {module === "activity" ? (
          <section className="panel stack" aria-labelledby="activity-title">
            <h2 id="activity-title" className="panel-title">
              Activity
            </h2>
            <p className="panel-hint">Real clinic events only. Secrets are never shown.</p>
            {activity.length === 0 ? (
              <p className="meta">No activity yet.</p>
            ) : (
              <ul className="data-list">
                {activity.map((row) => (
                  <li key={row.id}>
                    <strong>{row.action}</strong>
                    <p className="meta">
                      {row.actor_type} · {row.entity_type}
                      {row.entity_id ? ` · ${row.entity_id.slice(0, 8)}…` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}

        {module === "ai" ? <AiReceptionistPanel accessToken={accessToken} /> : null}

        {module === "analytics" ? (
          <section className="panel stack" aria-labelledby="analytics-title">
            <h2 id="analytics-title" className="panel-title">
              Analytics
            </h2>
            <p className="panel-hint">
              Real counts from this clinic only. No revenue charts or invented metrics.
            </p>
            {analytics ? (
              <>
                <ul className="count-grid">
                  <li>
                    <strong>{analytics.consultations_count}</strong>
                    <span>Consultations</span>
                  </li>
                  <li>
                    <strong>{analytics.customers_count}</strong>
                    <span>Customers</span>
                  </li>
                  <li>
                    <strong>{analytics.appointments_count}</strong>
                    <span>Appointments</span>
                  </li>
                  <li>
                    <strong>{analytics.open_handovers_count}</strong>
                    <span>Open handovers</span>
                  </li>
                  <li>
                    <strong>{analytics.conversations_count}</strong>
                    <span>Conversations</span>
                  </li>
                  <li>
                    <strong>{analytics.integrations_active_count}</strong>
                    <span>Active keys</span>
                  </li>
                </ul>
                <p className="meta">
                  Source: {analytics.source} · activity events {analytics.activity_count}
                </p>
              </>
            ) : (
              <p className="meta">Loading counts…</p>
            )}
          </section>
        ) : null}

        {module === "appointments" ? (
          <AppointmentsPanel
            accessToken={accessToken}
            clinicTimezone={clinic.timezone}
            prefillCustomerId={bookCustomerId}
            onBooked={() => void refresh()}
          />
        ) : null}
      </main>
    </div>
  );
}
