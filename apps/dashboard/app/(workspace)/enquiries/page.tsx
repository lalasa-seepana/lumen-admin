"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import { fetchConsultations } from "@/lib/api";
import type { ConsultationItem } from "@/lib/types";

export default function EnquiriesPage() {
  const { accessToken } = useAuth();
  const [rows, setRows] = useState<ConsultationItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      setRows(await fetchConsultations(accessToken));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not load enquiries. Refresh to try again.",
      );
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <>
      <PageHeader
        title="Enquiries"
        description="Website form submissions linked to patient records."
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
            <p className="meta">Loading enquiries…</p>
          ) : rows.length === 0 ? (
            <div className="empty-state">
              <strong>No enquiries yet</strong>
              Create an enquiry key under Integrations, connect that key from your clinic website, then sync or
              submit a form on the website. Clinic Dial only shows enquiries from the connected site.
            </div>
          ) : (
            <ul className="data-list">
              {rows.map((row) => (
                <li key={row.id}>
                  <Link href={`/patients?id=${row.customer_id}`} className="text-link">
                    {row.customer_name}
                  </Link>
                  <p className="meta">
                    {row.customer_email} · {row.category}
                    {row.service_name ? ` · ${row.service_name}` : ""} · {row.source_website}
                  </p>
                  <p className="meta">{new Date(row.created_at).toLocaleString()}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
