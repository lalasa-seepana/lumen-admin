"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import { fetchCustomer, fetchCustomers } from "@/lib/api";
import type { CustomerDetail, CustomerItem } from "@/lib/types";

function PatientsInner() {
  const { accessToken } = useAuth();
  const search = useSearchParams();
  const [rows, setRows] = useState<CustomerItem[] | null>(null);
  const [selected, setSelected] = useState<CustomerDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      setRows(await fetchCustomers(accessToken));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not load patients. Refresh to try again.",
      );
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const id = search.get("id");
    if (!id || !accessToken) return;
    void (async () => {
      try {
        setSelected(await fetchCustomer(accessToken, id));
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "We could not open that patient record.",
        );
      }
    })();
  }, [accessToken, search]);

  async function openPatient(id: string) {
    if (!accessToken) return;
    try {
      setSelected(await fetchCustomer(accessToken, id));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not open that patient record.",
      );
    }
  }

  return (
    <>
      {error ? <p className="error">{error}</p> : null}
      <section className="panel stack">
        {selected ? (
          <>
            <button type="button" className="text-link" onClick={() => setSelected(null)}>
              Back to all patients
            </button>
            <h2 className="panel-title">{selected.full_name}</h2>
            <p className="meta">
              {selected.email_normalized}
              {selected.phone_e164 ? ` · ${selected.phone_e164}` : ""}
              {selected.possible_phone_duplicate ? " · Possible shared phone number" : ""}
            </p>
            <h3 className="panel-subtitle">Enquiry history</h3>
            {selected.consultations.length === 0 ? (
              <p className="meta">No enquiries for this patient yet.</p>
            ) : (
              <ul className="data-list">
                {selected.consultations.map((row) => (
                  <li key={row.id}>
                    <strong>{row.category}</strong>
                    <p className="meta">
                      {row.service_name ?? "Service not named"} · {new Date(row.created_at).toLocaleString()}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <Link href={`/calendar?customer=${selected.id}`} className="btn" style={{ textAlign: "center" }}>
              Create appointment
            </Link>
          </>
        ) : rows === null ? (
          <p className="meta">Loading patients…</p>
        ) : rows.length === 0 ? (
          <div className="empty-state">
            <strong>No patients yet</strong>
            Patient records appear when your connected website syncs or forwards an enquiry.
          </div>
        ) : (
          <ul className="data-list">
            {rows.map((row) => (
              <li key={row.id}>
                <button type="button" className="text-link" onClick={() => void openPatient(row.id)}>
                  {row.full_name}
                </button>
                <p className="meta">
                  {row.email_normalized} · {row.consultation_count} enquir
                  {row.consultation_count === 1 ? "y" : "ies"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
      <div className="row">
        <button type="button" className="secondary" onClick={() => void refresh()}>
          Refresh list
        </button>
      </div>
    </>
  );
}

export default function PatientsPage() {
  return (
    <>
      <PageHeader
        title="Patients"
        description="People with enquiries or appointments at your clinic."
      />
      <div className="page-body">
        <Suspense fallback={<p className="meta">Loading patients…</p>}>
          <PatientsInner />
        </Suspense>
      </div>
    </>
  );
}
