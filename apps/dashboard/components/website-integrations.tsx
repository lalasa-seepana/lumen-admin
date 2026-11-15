"use client";

import { useEffect, useState } from "react";
import {
  createIntegration,
  listIntegrationActivity,
  listIntegrations,
  revokeIntegration,
} from "@/lib/api";
import type { Integration, IntegrationActivity, IntegrationCreated } from "@/lib/types";

type Props = {
  accessToken: string;
  clinicName?: string | null;
  onConnectionChange?: (connected: boolean) => void;
};

export function WebsiteIntegrations({ accessToken, clinicName, onConnectionChange }: Props) {
  const [rows, setRows] = useState<Integration[]>([]);
  const [activity, setActivity] = useState<IntegrationActivity[]>([]);
  const [minted, setMinted] = useState<IntegrationCreated | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function refresh() {
    const [integrations, events] = await Promise.all([
      listIntegrations(accessToken),
      listIntegrationActivity(accessToken),
    ]);
    setRows(integrations);
    setActivity(events);
    onConnectionChange?.(integrations.some((row) => !row.revoked_at));
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [integrations, events] = await Promise.all([
          listIntegrations(accessToken),
          listIntegrationActivity(accessToken),
        ]);
        if (!cancelled) {
          setRows(integrations);
          setActivity(events);
          onConnectionChange?.(integrations.some((row) => !row.revoked_at));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "We could not load enquiry keys. Refresh to try again.",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, onConnectionChange]);

  async function onMint() {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const created = await createIntegration(accessToken, { label: "Website" });
      setMinted(created);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not create an enquiry key. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: string) {
    const confirmed = window.confirm(
      "Revoke this enquiry key? Your website will stop forwarding new enquiries until you create a new key and reconnect from the website.",
    );
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      await revokeIntegration(accessToken, id);
      if (minted?.id === id) setMinted(null);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not revoke that key. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onCopy() {
    if (!minted?.api_key) return;
    try {
      await navigator.clipboard.writeText(minted.api_key);
      setCopied(true);
    } catch {
      setError("Clipboard access failed. Select the key and copy it manually.");
    }
  }

  const hasActiveKey = rows.some((row) => !row.revoked_at);
  const isLumenClinic = (clinicName ?? "").trim().toLowerCase() === "lumen";

  return (
    <section className="panel stack workspace-panel" aria-labelledby="integrations-title">
      <div>
        <h2 id="integrations-title" className="panel-title">
          Enquiry forwarding
        </h2>
        <p className="panel-hint">
          Create a key for <strong>{clinicName || "this clinic"}</strong>, then finish the connection on that
          clinic’s own website. Enquiries appear here only after that website connects with this clinic’s key.
          Another website’s patients never mix in.
        </p>
      </div>

      <ol className="meta" style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.6 }}>
        <li>Create an enquiry key in Clinic Dial while signed into the correct clinic.</li>
        <li>
          On that clinic’s website connect screen, paste the key.
          {isLumenClinic ? (
            <>
              {" "}
              For this Lumen clinic that is{" "}
              <a href="http://localhost:3000/connect" target="_blank" rel="noreferrer">
                localhost:3000/connect
              </a>
              .
            </>
          ) : (
            <> Lumen’s connect page will refuse this key unless the clinic is named Lumen.</>
          )}
        </li>
        <li>The website syncs its stored enquiries into this clinic only.</li>
      </ol>

      <div className="row">
        <button type="button" disabled={busy} onClick={onMint}>
          {busy ? "Creating key…" : "Create enquiry key"}
        </button>
      </div>

      {minted ? (
        <div className="key-once" role="status" aria-live="polite">
          <p className="meta">
            New key <code>{minted.key_prefix}</code>. Copy it now, then paste it on your website’s connect page.
            Clinic Dial will not show the full value again.
          </p>
          <code className="key-value">{minted.api_key}</code>
          <div className="row">
            <button type="button" className="secondary" disabled={busy} onClick={onCopy}>
              {copied ? "Copied" : "Copy key"}
            </button>
            {isLumenClinic ? (
              <a
                className="btn secondary"
                href="http://localhost:3000/connect"
                target="_blank"
                rel="noreferrer"
              >
                Open Lumen connect
              </a>
            ) : null}
            <button type="button" className="secondary" disabled={busy} onClick={() => setMinted(null)}>
              Dismiss
            </button>
          </div>
        </div>
      ) : null}

      <ul className="integration-list">
        {rows.length === 0 ? (
          <li className="meta">No enquiry keys yet. Create one, then connect from your website.</li>
        ) : (
          rows.map((row) => (
            <li key={row.id} className="integration-row">
              <div>
                <strong>{row.label}</strong>
                <p className="meta">
                  Prefix <code>{row.key_prefix}</code>
                  {row.revoked_at ? " · Revoked" : " · Active"}
                </p>
              </div>
              {!row.revoked_at ? (
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void onRevoke(row.id)}
                >
                  Revoke key
                </button>
              ) : null}
            </li>
          ))
        )}
      </ul>

      {!hasActiveKey ? (
        <p className="meta">
          Calendar providers unlock after you create an enquiry key and connect your website.
        </p>
      ) : null}

      <div>
        <h3 className="panel-subtitle">Recent enquiry activity</h3>
        <ul className="activity-list">
          {activity.length === 0 ? (
            <li className="meta">No submissions received yet. Connect your website, then sync or submit a form there.</li>
          ) : (
            activity.slice(0, 12).map((event) => (
              <li key={event.id}>
                <span className={`status-pill status-${event.status}`}>{event.status}</span>
                <span className="meta">
                  {event.reason ? ` · ${event.reason}` : ""}
                  {event.idempotency_key ? ` · ${event.idempotency_key.slice(0, 8)}…` : ""}
                </span>
              </li>
            ))
          )}
        </ul>
      </div>

      {error ? (
        <p className="error" role="alert" aria-live="assertive">
          {error}
        </p>
      ) : null}
    </section>
  );
}
