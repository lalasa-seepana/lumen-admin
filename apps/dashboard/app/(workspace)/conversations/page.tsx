"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import { deleteConversation, fetchConversation, fetchConversations } from "@/lib/api";
import type { ConversationDetail, ConversationItem } from "@/lib/types";

export default function ConversationsPage() {
  const { accessToken } = useAuth();
  const [rows, setRows] = useState<ConversationItem[] | null>(null);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      setRows(await fetchConversations(accessToken));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not load conversations. Refresh to try again.",
      );
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function openConversation(id: string) {
    if (!accessToken) return;
    setBusy(true);
    try {
      setSelected(await fetchConversation(accessToken, id));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not open that transcript.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string) {
    if (!accessToken) return;
    const confirmed = window.confirm(
      "Delete this transcript? The conversation record stays, but the permitted text is removed.",
    );
    if (!confirmed) return;
    setBusy(true);
    try {
      await deleteConversation(accessToken, id);
      setSelected(null);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not delete that transcript. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Conversations"
        description="Visitor receptionist sessions. Transcripts appear only when recording consent was given."
        actions={
          <button type="button" className="secondary" onClick={() => void refresh()}>
            Refresh
          </button>
        }
      />
      <div className="page-body">
        {error ? <p className="error">{error}</p> : null}
        <section className="panel stack">
          {rows === null ? (
            <p className="meta">Loading conversations…</p>
          ) : rows.length === 0 ? (
            <div className="empty-state">
              <strong>No conversations yet</strong>
              Open Receptionist to test the visitor experience. Consented sessions appear here.
            </div>
          ) : (
            <ul className="data-list">
              {rows.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className="text-link"
                    disabled={busy}
                    onClick={() => void openConversation(row.id)}
                  >
                    {row.language} · {new Date(row.created_at).toLocaleString()}
                  </button>
                  <p className="meta">
                    {row.transcript_available
                      ? `${row.turn_count} turn${row.turn_count === 1 ? "" : "s"}`
                      : "Transcript not available (no recording consent)"}
                    {row.handover_count
                      ? ` · ${row.handover_count} handover${row.handover_count === 1 ? "" : "s"}`
                      : ""}
                    {row.appointment_count
                      ? ` · ${row.appointment_count} booking${row.appointment_count === 1 ? "" : "s"}`
                      : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        {selected ? (
          <section className="panel stack" aria-labelledby="transcript-title">
            <h2 id="transcript-title" className="panel-title">
              Transcript
            </h2>
            <p className="meta">{selected.retention_note}</p>
            {selected.appointments?.length ? (
              <div className="stack">
                <h3 className="panel-title">Booked from this conversation</h3>
                <ul className="data-list">
                  {selected.appointments.map((appt) => (
                    <li key={appt.id}>
                      <strong>
                        {appt.service_name} · {appt.status}
                      </strong>
                      <p className="meta">
                        {appt.customer_name} · {appt.starts_at_clinic} – {appt.ends_at_clinic} (
                        {appt.clinic_timezone})
                      </p>
                    </li>
                  ))}
                </ul>
                <Link className="text-link" href="/calendar">
                  Open calendar
                </Link>
              </div>
            ) : null}
            {selected.transcript_available ? (
              selected.turns.length === 0 ? (
                <p className="meta">This session has consent, but no messages yet.</p>
              ) : (
                <ul className="data-list">
                  {selected.turns.map((turn) => (
                    <li key={turn.id}>
                      <strong>{turn.role}</strong>
                      <p>{turn.text}</p>
                    </li>
                  ))}
                </ul>
              )
            ) : (
              <p className="meta">No transcript is available for this session.</p>
            )}
            <div className="row">
              <button type="button" className="secondary" onClick={() => setSelected(null)}>
                Close transcript
              </button>
              {selected.transcript_available ? (
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void onDelete(selected.id)}
                >
                  Delete transcript
                </button>
              ) : null}
            </div>
          </section>
        ) : null}
      </div>
    </>
  );
}
