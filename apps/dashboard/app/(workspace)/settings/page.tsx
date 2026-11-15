"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import { fetchActivity } from "@/lib/api";
import type { ActivityEvent } from "@/lib/types";

export default function SettingsPage() {
  const { me, refreshMe } = useAuth();
  const [activity, setActivity] = useState<ActivityEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshMe().catch(() => {
      /* keep existing me */
    });
  }, [refreshMe]);

  useEffect(() => {
    void (async () => {
      try {
        const { getSupabase } = await import("@/lib/supabase");
        const { data } = await getSupabase().auth.getSession();
        const token = data.session?.access_token;
        if (!token) return;
        setActivity(await fetchActivity(token));
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "We could not load activity. Refresh to try again.",
        );
      }
    })();
  }, []);

  const clinic = me?.clinic;

  return (
    <>
      <PageHeader
        title="Settings"
        description="Clinic profile, account details, and recent activity."
      />
      <div className="page-body">
        {error ? <p className="error">{error}</p> : null}
        <section className="panel stack">
          <h2 className="panel-title">Clinic profile</h2>
          {clinic ? (
            <>
              <p>
                <strong>{clinic.name}</strong>
              </p>
              <p className="meta">Timezone: {clinic.timezone}</p>
              <p className="meta">Clinic ID: {clinic.id}</p>
              <p className="meta">Created: {new Date(clinic.created_at).toLocaleString()}</p>
            </>
          ) : (
            <p className="meta">Clinic details are not loaded yet.</p>
          )}
        </section>
        <section className="panel stack">
          <h2 className="panel-title">Account</h2>
          <p className="meta">{me?.email ?? me?.user_id}</p>
          <p className="meta">Role: {me?.membership?.role ?? "Not set"}</p>
        </section>
        <section className="panel stack">
          <h2 className="panel-title">Activity history</h2>
          {activity === null ? (
            <p className="meta">Loading activity…</p>
          ) : activity.length === 0 ? (
            <div className="empty-state">
              <strong>No activity yet</strong>
              Actions in your clinic will appear here as they happen.
            </div>
          ) : (
            <ul className="data-list">
              {activity.map((row) => (
                <li key={row.id}>
                  <strong>{row.action}</strong>
                  <p className="meta">
                    {row.actor_type} · {row.entity_type} · {new Date(row.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
