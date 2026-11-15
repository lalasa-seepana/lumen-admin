"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import {
  createService,
  fetchImportDrafts,
  fetchServices,
  reviewImportDraft,
} from "@/lib/api";
import type { ClinicService, ServiceImportDraft } from "@/lib/types";

export default function ServicesPage() {
  const { accessToken } = useAuth();
  const [services, setServices] = useState<ClinicService[] | null>(null);
  const [drafts, setDrafts] = useState<ServiceImportDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("General");
  const [duration, setDuration] = useState(60);
  const [pricePaise, setPricePaise] = useState("");

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      const [svc, draftRows] = await Promise.all([
        fetchServices(accessToken),
        fetchImportDrafts(accessToken).catch(() => [] as ServiceImportDraft[]),
      ]);
      setServices(svc);
      setDrafts(draftRows.filter((d) => d.status === "pending"));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not load services. Refresh to try again.",
      );
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setBusy(true);
    try {
      await createService(accessToken, {
        name,
        category,
        duration_minutes: duration,
        price_paise: pricePaise ? Number(pricePaise) : undefined,
      });
      setName("");
      setNotice(`“${name.trim()}” is now in your bookable catalogue.`);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not add that service. Check the fields and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onReview(id: string, action: "approve" | "reject", draft?: ServiceImportDraft) {
    if (!accessToken) return;
    setBusy(true);
    try {
      const edits: Record<string, unknown> = {};
      if (action === "approve" && draft) {
        if (!draft.name) {
          const prompted = window.prompt("Service name");
          if (!prompted) {
            setBusy(false);
            return;
          }
          edits.name = prompted;
        }
        if (draft.duration_minutes == null) {
          const raw = window.prompt("Duration in minutes (required for booking)");
          const mins = raw ? Number(raw) : NaN;
          if (!Number.isFinite(mins) || mins <= 0) {
            setError("Enter a valid duration in minutes before approving.");
            setBusy(false);
            return;
          }
          edits.duration_minutes = mins;
        }
      }
      await reviewImportDraft(accessToken, id, {
        action,
        edits: Object.keys(edits).length ? edits : undefined,
      });
      setNotice(
        action === "approve"
          ? "Draft approved. It is now a bookable service."
          : "Draft rejected. It will not appear in the catalogue.",
      );
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not update that draft. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Services"
        description="Approved services visitors can book. Review imported drafts before they go live."
      />
      <div className="page-body">
        {error ? <p className="error">{error}</p> : null}
        {notice ? <p className="notice">{notice}</p> : null}

        {drafts.length > 0 ? (
          <section className="panel stack">
            <h2 className="panel-title">Import review</h2>
            <p className="panel-hint">
              These are drafts from your website. Approve only what your clinic offers. Missing fields stay blank until you add them.
            </p>
            <ul className="data-list">
              {drafts.map((d) => (
                <li key={d.id}>
                  <strong>{d.name ?? "Untitled draft"}</strong>
                  <p className="meta">
                    {d.duration_minutes != null ? `${d.duration_minutes} min` : "Duration not set"}
                    {d.price_paise != null ? ` · ₹${(d.price_paise / 100).toFixed(0)}` : ""}
                    {d.source_url ? ` · ${d.source_url}` : ""}
                  </p>
                  {d.description ? <p className="meta">{d.description}</p> : null}
                  <div className="row">
                    <button type="button" disabled={busy} onClick={() => void onReview(d.id, "approve", d)}>
                      Approve draft
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      disabled={busy}
                      onClick={() => void onReview(d.id, "reject", d)}
                    >
                      Reject draft
                    </button>
                  </div>
                  {d.duration_minutes == null ? (
                    <p className="meta">Duration is required before booking. You will be asked when you approve.</p>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <section className="panel stack">
          <h2 className="panel-title">Bookable catalogue</h2>
          {services === null ? (
            <p className="meta">Loading services…</p>
          ) : services.length === 0 ? (
            <div className="empty-state">
              <strong>No bookable services yet</strong>
              Add a service below, or import drafts from Website.
            </div>
          ) : (
            <ul className="data-list">
              {services.map((row) => (
                <li key={row.id}>
                  <strong>{row.name}</strong>
                  <p className="meta">
                    {row.category} · {row.duration_minutes} min
                    {row.price_paise != null ? ` · ₹${(row.price_paise / 100).toFixed(0)}` : ""}
                    {row.source_url ? ` · From ${row.source_url}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel stack">
          <h2 className="panel-title">Add service</h2>
          <form className="stack" onSubmit={onCreate}>
            <label>
              Name
              <input required value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              Category
              <input required value={category} onChange={(e) => setCategory(e.target.value)} />
            </label>
            <label>
              Duration (minutes)
              <input
                type="number"
                min={15}
                max={480}
                required
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </label>
            <label>
              Price in paise (optional)
              <input
                type="number"
                min={0}
                value={pricePaise}
                onChange={(e) => setPricePaise(e.target.value)}
                placeholder="Leave blank if you do not publish a price"
              />
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Adding service…" : "Add service"}
            </button>
          </form>
        </section>
      </div>
    </>
  );
}
