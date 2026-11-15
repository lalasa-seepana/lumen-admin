"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  cancelAppointment,
  createAppointment,
  createAvailability,
  createService,
  fetchAppointments,
  fetchAvailability,
  fetchCustomers,
  fetchServices,
} from "@/lib/api";
import type { AppointmentItem, AvailabilityWindow, ClinicService, CustomerItem } from "@/lib/types";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Props = {
  accessToken: string;
  clinicTimezone: string;
  prefillCustomerId?: string | null;
  onBooked?: () => void;
};

function minutesLabel(value: number): string {
  const h = Math.floor(value / 60)
    .toString()
    .padStart(2, "0");
  const m = (value % 60).toString().padStart(2, "0");
  return `${h}:${m}`;
}

export function AppointmentsPanel({
  accessToken,
  clinicTimezone,
  prefillCustomerId = null,
  onBooked,
}: Props) {
  const [services, setServices] = useState<ClinicService[]>([]);
  const [windows, setWindows] = useState<AvailabilityWindow[]>([]);
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [serviceName, setServiceName] = useState("Aroma Swedish Massage");
  const [serviceCategory, setServiceCategory] = useState("Heal Your Mind");
  const [duration, setDuration] = useState(60);
  const [weekday, setWeekday] = useState(0);
  const [startMinute, setStartMinute] = useState(10 * 60);
  const [endMinute, setEndMinute] = useState(18 * 60);
  const [customerId, setCustomerId] = useState(prefillCustomerId ?? "");
  const [serviceId, setServiceId] = useState("");
  const [localStart, setLocalStart] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [svc, avail, appts, cust] = await Promise.all([
        fetchServices(accessToken),
        fetchAvailability(accessToken),
        fetchAppointments(accessToken),
        fetchCustomers(accessToken),
      ]);
      setServices(svc);
      setWindows(avail);
      setAppointments(appts);
      setCustomers(cust);
      if (!serviceId && svc[0]) setServiceId(svc[0].id);
      if (!customerId && (prefillCustomerId || cust[0])) {
        setCustomerId(prefillCustomerId || cust[0].id);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load appointments");
    }
  }, [accessToken, customerId, prefillCustomerId, serviceId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (prefillCustomerId) setCustomerId(prefillCustomerId);
  }, [prefillCustomerId]);

  async function onCreateService(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      const row = await createService(accessToken, {
        name: serviceName,
        category: serviceCategory,
        duration_minutes: duration,
      });
      setServiceId(row.id);
      setNotice(`Service “${row.name}” created.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create service");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateWindow(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      await createAvailability(accessToken, {
        weekday,
        start_minute: startMinute,
        end_minute: endMinute,
      });
      setNotice("Availability window added.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add availability");
    } finally {
      setBusy(false);
    }
  }

  async function onBook(event: FormEvent) {
    event.preventDefault();
    if (!localStart) {
      setError("Pick a start time in clinic timezone.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      // datetime-local is clinic-wall time without offset; interpret as Asia/Kolkata for POC.
      const asUtc = new Date(`${localStart}:00+05:30`).toISOString();
      const row = await createAppointment(accessToken, {
        customer_id: customerId,
        service_id: serviceId,
        starts_at_utc: asUtc,
      });
      setNotice(`Booked ${row.service_name} for ${row.customer_name} (${row.starts_at_clinic}).`);
      await refresh();
      onBooked?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not book appointment");
    } finally {
      setBusy(false);
    }
  }

  async function onCancel(id: string) {
    setBusy(true);
    try {
      await cancelAppointment(accessToken, id);
      setNotice("Appointment cancelled. The time slot is free again.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not cancel");
    } finally {
      setBusy(false);
    }
  }

  const upcoming = appointments.filter((row) => row.status !== "cancelled");

  return (
    <section className="panel stack" aria-labelledby="appointments-title">
      <h2 id="appointments-title" className="panel-title">
        Appointments
      </h2>
      <p className="panel-hint">
        Services, availability, and bookings for this clinic. Times stored UTC; shown in{" "}
        {clinicTimezone}. Overlaps are rejected.
      </p>

      {error ? (
        <p className="error" role="alert" aria-live="assertive">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="notice" role="status" aria-live="polite">
          {notice}
        </p>
      ) : null}

      <div className="stack">
        <h3 className="panel-title">Services</h3>
        <form className="stack" onSubmit={onCreateService}>
          <label>
            Name
            <input required value={serviceName} onChange={(e) => setServiceName(e.target.value)} />
          </label>
          <label>
            Category
            <input
              required
              value={serviceCategory}
              onChange={(e) => setServiceCategory(e.target.value)}
            />
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
          <button type="submit" disabled={busy}>
            Add service
          </button>
        </form>
        {services.length === 0 ? (
          <p className="meta">No services yet.</p>
        ) : (
          <ul className="data-list">
            {services.map((row) => (
              <li key={row.id}>
                <strong>{row.name}</strong>
                <p className="meta">
                  {row.category} · {row.duration_minutes} min
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="stack">
        <h3 className="panel-title">Availability</h3>
        <form className="stack" onSubmit={onCreateWindow}>
          <label>
            Weekday
            <select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
              {WEEKDAYS.map((label, index) => (
                <option key={label} value={index}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Start (minutes from midnight UTC window basis)
            <input
              type="number"
              min={0}
              max={1439}
              value={startMinute}
              onChange={(e) => setStartMinute(Number(e.target.value))}
            />
          </label>
          <label>
            End
            <input
              type="number"
              min={1}
              max={1440}
              value={endMinute}
              onChange={(e) => setEndMinute(Number(e.target.value))}
            />
          </label>
          <button type="submit" disabled={busy}>
            Add window
          </button>
        </form>
        <p className="meta">
          Example: Mon 600–1080 → 10:00–18:00. Empty windows = open schedule (conflicts still apply).
        </p>
        {windows.length === 0 ? (
          <p className="meta">No windows configured.</p>
        ) : (
          <ul className="data-list">
            {windows.map((row) => (
              <li key={row.id}>
                <strong>{WEEKDAYS[row.weekday]}</strong>
                <p className="meta">
                  {minutesLabel(row.start_minute)}–{minutesLabel(row.end_minute)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="stack">
        <h3 className="panel-title">Book appointment</h3>
        <form className="stack" onSubmit={onBook}>
          <label>
            Customer
            <select
              required
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              disabled={customers.length === 0}
            >
              {customers.length === 0 ? <option value="">No customers</option> : null}
              {customers.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Service
            <select
              required
              value={serviceId}
              onChange={(e) => setServiceId(e.target.value)}
              disabled={services.length === 0}
            >
              {services.length === 0 ? <option value="">Add a service first</option> : null}
              {services.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name} ({row.duration_minutes}m)
                </option>
              ))}
            </select>
          </label>
          <label>
            Start ({clinicTimezone})
            <input
              type="datetime-local"
              required
              value={localStart}
              onChange={(e) => setLocalStart(e.target.value)}
            />
          </label>
          <button type="submit" disabled={busy || !customerId || !serviceId}>
            Book
          </button>
        </form>
      </div>

      <div className="stack">
        <h3 className="panel-title">Schedule</h3>
        {upcoming.length === 0 ? (
          <p className="meta">No active appointments.</p>
        ) : (
          <ul className="data-list">
            {upcoming.map((row) => (
              <li key={row.id}>
                <strong>
                  {row.starts_at_clinic} · {row.service_name}
                </strong>
                <p className="meta">
                  {row.customer_name} · {row.status} · UTC {new Date(row.starts_at_utc).toISOString()}
                </p>
                {row.status !== "cancelled" ? (
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() => void onCancel(row.id)}
                  >
                    Cancel
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
