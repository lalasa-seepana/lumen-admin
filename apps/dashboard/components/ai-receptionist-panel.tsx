"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  deleteConversation,
  fetchConversation,
  fetchConversations,
  fetchHandovers,
  updateHandoverStatus,
} from "@/lib/api";
import type { ConversationDetail, ConversationItem, HandoverItem } from "@/lib/types";

type Props = {
  accessToken: string;
};

export function AiReceptionistPanel({ accessToken }: Props) {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [handovers, setHandovers] = useState<HandoverItem[]>([]);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [conv, hand] = await Promise.all([
        fetchConversations(accessToken),
        fetchHandovers(accessToken),
      ]);
      setConversations(conv);
      setHandovers(hand);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load AI receptionist data");
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function openConversation(id: string) {
    setBusy(true);
    try {
      setSelected(await fetchConversation(accessToken, id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transcript");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string) {
    setBusy(true);
    try {
      await deleteConversation(accessToken, id);
      setSelected(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete conversation");
    } finally {
      setBusy(false);
    }
  }

  async function onHandoverStatus(id: string, status: HandoverItem["status"]) {
    setBusy(true);
    try {
      await updateHandoverStatus(accessToken, id, status);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update handover");
    } finally {
      setBusy(false);
    }
  }

  const openHandovers = handovers.filter((row) => row.status === "open");

  return (
    <section className="panel stack" aria-labelledby="ai-title">
      <h2 id="ai-title" className="panel-title">
        AI receptionist
      </h2>
      <p className="panel-hint">
        Consented transcripts and handovers from visitor sessions. Audio is not kept without recording
        consent. Transcripts are retained for up to 90 days by default.
      </p>
      <p className="meta">
        Open the visitor receptionist from Receptionist settings to start a session.
      </p>

      {error ? (
        <p className="error" role="alert" aria-live="assertive">
          {error}
        </p>
      ) : null}

      <div className="stack">
        <h3 className="panel-title">Handover inbox</h3>
        {handovers.length === 0 ? (
          <p className="meta">No handovers yet. Escalations from voice appear here.</p>
        ) : (
          <>
            <p className="meta">
              {openHandovers.length} open · {handovers.length} total
            </p>
            <ul className="data-list">
              {handovers.map((row) => (
                <li key={row.id}>
                  <strong>{row.reason}</strong>
                  <p className="meta">
                    {row.status} · {new Date(row.created_at).toLocaleString()}
                  </p>
                  <p>{row.summary}</p>
                  <div className="row">
                    {row.status === "open" ? (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void onHandoverStatus(row.id, "acked")}
                      >
                        Acknowledge
                      </button>
                    ) : null}
                    {row.status !== "closed" ? (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void onHandoverStatus(row.id, "closed")}
                      >
                        Close
                      </button>
                    ) : null}
                    {row.conversation_id ? (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void openConversation(row.conversation_id!)}
                      >
                        Open conversation
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div className="stack">
        <h3 className="panel-title">Conversations</h3>
        {conversations.length === 0 ? (
          <p className="meta">No conversations yet.</p>
        ) : (
          <ul className="data-list">
            {conversations.map((row) => (
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
                    ? `${row.turn_count} turns`
                    : "Transcript withheld (no recording consent)"}
                  {row.handover_count ? ` · ${row.handover_count} handover(s)` : ""}
                  {row.appointment_count ? ` · ${row.appointment_count} booking(s)` : ""}
                  {` · retain until ${new Date(row.retention_until).toLocaleDateString()}`}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selected ? (
        <div className="stack" aria-labelledby="transcript-title">
          <h3 id="transcript-title" className="panel-title">
            Transcript
          </h3>
          <p className="meta">{selected.retention_note}</p>
          {selected.appointments?.length ? (
            <div className="stack">
              <h4 className="panel-title">Booked from this conversation</h4>
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
              <p className="meta">Consented session with no turns yet.</p>
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
            <p className="meta">Transcript not available for this session.</p>
          )}
          <div className="row">
            <button type="button" className="secondary" disabled={busy} onClick={() => setSelected(null)}>
              Close transcript
            </button>
            {selected.transcript_available ? (
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => void onDelete(selected.id)}
              >
                Delete on request
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
