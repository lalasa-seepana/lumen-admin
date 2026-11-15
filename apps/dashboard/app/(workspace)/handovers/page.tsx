"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import { fetchHandovers, updateHandoverStatus } from "@/lib/api";
import type { HandoverItem } from "@/lib/types";

export default function HandoversPage() {
  const { accessToken } = useAuth();
  const [rows, setRows] = useState<HandoverItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      setRows(await fetchHandovers(accessToken));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not load handovers. Refresh to try again.",
      );
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onStatus(id: string, status: HandoverItem["status"]) {
    if (!accessToken) return;
    setBusy(true);
    try {
      await updateHandoverStatus(accessToken, id, status);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not update that handover. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Handovers"
        description="Visitors who asked to speak with someone on your team."
        actions={
          <button type="button" className="secondary" onClick={() => void refresh()}>
            Refresh
          </button>
        }
      />
      <div className="page-body">
        {error ? <p className="error">{error}</p> : null}
        <section className="panel">
          {rows === null ? (
            <p className="meta">Loading handovers…</p>
          ) : rows.length === 0 ? (
            <div className="empty-state">
              <strong>No handovers yet</strong>
              When the receptionist escalates a visitor, the request appears here.
            </div>
          ) : (
            <ul className="data-list">
              {rows.map((row) => (
                <li key={row.id}>
                  <div className="row">
                    <strong>{row.reason}</strong>
                    <span className={`status-pill status-${row.status}`}>{row.status}</span>
                  </div>
                  <p className="meta">{new Date(row.created_at).toLocaleString()}</p>
                  <p>{row.summary}</p>
                  <div className="row">
                    {row.status === "open" ? (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void onStatus(row.id, "acked")}
                      >
                        Mark as seen
                      </button>
                    ) : null}
                    {row.status !== "closed" ? (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void onStatus(row.id, "closed")}
                      >
                        Close handover
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
