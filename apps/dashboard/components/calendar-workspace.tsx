"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  cancelAppointment,
  createAppointment,
  createAvailability,
  fetchAppointments,
  fetchAvailability,
  fetchCustomers,
  fetchServices,
  rescheduleAppointment,
} from "@/lib/api";
import type { AppointmentItem, AvailabilityWindow, ClinicService, CustomerItem } from "@/lib/types";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
type ViewMode = "day" | "week" | "month" | "agenda";

type Props = {
  accessToken: string;
  clinicTimezone: string;
};

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function clinicParts(d: Date, timezone: string): Record<string, string> {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return Object.fromEntries(
    fmt.formatToParts(d).filter((p) => p.type !== "literal").map((p) => [p.type, p.value]),
  );
}

function utcIsoToClinicLocalInput(iso: string, timezone: string): string {
  const parts = clinicParts(new Date(iso), timezone);
  const hour = (Number(parts.hour) % 24).toString().padStart(2, "0");
  return `${parts.year}-${parts.month}-${parts.day}T${hour}:${parts.minute}`;
}

function nowClinicLocalInput(timezone: string): string {
  return utcIsoToClinicLocalInput(new Date().toISOString(), timezone);
}

function formatLocalInput(d: Date, timezone: string): string {
  return utcIsoToClinicLocalInput(d.toISOString(), timezone);
}

function clinicDayKey(d: Date, timezone: string): string {
  const parts = clinicParts(d, timezone);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function clinicHour(d: Date, timezone: string): number {
  const parts = clinicParts(d, timezone);
  return Number(parts.hour) % 24;
}

function addCalendarMonths(d: Date, months: number): Date {
  const x = new Date(d);
  x.setMonth(x.getMonth() + months);
  return startOfDay(x);
}

function clinicLocalToUtcIso(localValue: string, timezone: string): string {
  // Interpret datetime-local as clinic wall clock via Intl offset sampling.
  const [datePart, timePart] = localValue.split("T");
  const provisional = new Date(`${datePart}T${timePart}:00Z`);
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  // Binary-search-ish: use formatter parts to find UTC that matches wall time.
  let guess = provisional.getTime();
  for (let i = 0; i < 3; i++) {
    const parts = Object.fromEntries(
      fmt.formatToParts(new Date(guess)).filter((p) => p.type !== "literal").map((p) => [p.type, p.value]),
    ) as Record<string, string>;
    const asUtc = Date.UTC(
      Number(parts.year),
      Number(parts.month) - 1,
      Number(parts.day),
      Number(parts.hour) % 24,
      Number(parts.minute),
      Number(parts.second || "0"),
    );
    const target = Date.UTC(
      Number(datePart.slice(0, 4)),
      Number(datePart.slice(5, 7)) - 1,
      Number(datePart.slice(8, 10)),
      Number(timePart.slice(0, 2)),
      Number(timePart.slice(3, 5)),
      0,
    );
    guess += target - asUtc;
  }
  return new Date(guess).toISOString();
}

function minutesFromTime(value: string): number {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

function timeFromMinutes(value: number): string {
  const h = Math.floor(value / 60)
    .toString()
    .padStart(2, "0");
  const m = (value % 60).toString().padStart(2, "0");
  return `${h}:${m}`;
}

export function CalendarWorkspace({ accessToken, clinicTimezone }: Props) {
  const search = useSearchParams();
  const [view, setView] = useState<ViewMode>("week");
  const [cursor, setCursor] = useState(() => startOfDay(new Date()));
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [services, setServices] = useState<ClinicService[]>([]);
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [windows, setWindows] = useState<AvailabilityWindow[]>([]);
  const [selected, setSelected] = useState<AppointmentItem | null>(null);
  const [drawerMode, setDrawerMode] = useState<"detail" | "create" | "hours" | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("active");
  const [serviceFilter, setServiceFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [customerId, setCustomerId] = useState(search.get("customer") ?? "");
  const [serviceId, setServiceId] = useState("");
  const [localStart, setLocalStart] = useState("");
  const [weekday, setWeekday] = useState(0);
  const [startTime, setStartTime] = useState("10:00");
  const [endTime, setEndTime] = useState("18:00");
  const [rescheduleLocal, setRescheduleLocal] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [appts, svc, cust, avail] = await Promise.all([
        fetchAppointments(accessToken),
        fetchServices(accessToken),
        fetchCustomers(accessToken),
        fetchAvailability(accessToken),
      ]);
      setAppointments(appts);
      setServices(svc);
      setCustomers(cust);
      setWindows(avail);
      if (!serviceId && svc[0]) setServiceId(svc[0].id);
      if (!customerId && (search.get("customer") || cust[0])) {
        setCustomerId(search.get("customer") || cust[0].id);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not load the calendar. Refresh to try again.");
    }
  }, [accessToken, customerId, search, serviceId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const filtered = useMemo(() => {
    return appointments.filter((row) => {
      if (statusFilter === "active" && row.status === "cancelled") return false;
      if (statusFilter !== "active" && statusFilter !== "all" && row.status !== statusFilter) return false;
      if (serviceFilter && row.service_id !== serviceFilter) return false;
      return true;
    });
  }, [appointments, serviceFilter, statusFilter]);

  const eventsByDay = useMemo(() => {
    const map = new Map<string, AppointmentItem[]>();
    for (const row of filtered) {
      const key = clinicDayKey(new Date(row.starts_at_utc), clinicTimezone);
      const list = map.get(key) ?? [];
      list.push(row);
      map.set(key, list);
    }
    return map;
  }, [filtered, clinicTimezone]);

  function dayKey(d: Date): string {
    return clinicDayKey(d, clinicTimezone);
  }

  async function onBook(event: FormEvent) {
    event.preventDefault();
    if (!localStart) {
      setError("Choose a start time in your clinic timezone.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const row = await createAppointment(accessToken, {
        customer_id: customerId,
        service_id: serviceId,
        starts_at_utc: clinicLocalToUtcIso(localStart, clinicTimezone),
      });
      setNotice(
        `Appointment saved for ${row.customer_name}. External calendar sync is separate and only appears when Google is connected.`,
      );
      setDrawerMode("detail");
      setSelected(row);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not create that appointment. Try another time.");
    } finally {
      setBusy(false);
    }
  }

  async function onCancel() {
    if (!selected) return;
    setBusy(true);
    try {
      const row = await cancelAppointment(accessToken, selected.id);
      setSelected(row);
      setNotice("Appointment cancelled. The time slot is free again.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not cancel that appointment. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function onReschedule(event: FormEvent) {
    event.preventDefault();
    if (!selected || !rescheduleLocal) return;
    setBusy(true);
    try {
      const row = await rescheduleAppointment(accessToken, selected.id, {
        starts_at_utc: clinicLocalToUtcIso(rescheduleLocal, clinicTimezone),
      });
      setSelected(row);
      setNotice("Appointment rescheduled.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not reschedule that appointment. Try another time.");
    } finally {
      setBusy(false);
    }
  }

  async function onAddHours(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await createAvailability(accessToken, {
        weekday,
        start_minute: minutesFromTime(startTime),
        end_minute: minutesFromTime(endTime),
      });
      setNotice("Opening hours saved in your clinic timezone.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not save opening hours. Check the times and try again.");
    } finally {
      setBusy(false);
    }
  }

  const monthStart = useMemo(() => {
    const d = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const dow = (d.getDay() + 6) % 7; // Monday=0
    return addDays(d, -dow);
  }, [cursor]);

  const weekStart = useMemo(() => {
    const dow = (cursor.getDay() + 6) % 7;
    return addDays(cursor, -dow);
  }, [cursor]);

  const titleLabel =
    view === "month"
      ? cursor.toLocaleString(undefined, { month: "long", year: "numeric" })
      : view === "week"
        ? `Week of ${weekStart.toLocaleDateString()}`
        : cursor.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });

  return (
    <div className="stack">
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p className="notice">{notice}</p> : null}

      <div className={`calendar-layout ${drawerMode ? "with-drawer" : ""}`}>
        <div className="calendar-board">
          <div className="calendar-toolbar">
            <div className="row">
              <button type="button" className="secondary" onClick={() => setCursor(startOfDay(new Date()))}>
                Go to today
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setCursor(
                    view === "month" ? addCalendarMonths(cursor, -1) : addDays(cursor, view === "week" ? -7 : -1),
                  )
                }
              >
                ←
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setCursor(
                    view === "month" ? addCalendarMonths(cursor, 1) : addDays(cursor, view === "week" ? 7 : 1),
                  )
                }
              >
                →
              </button>
              <strong>{titleLabel}</strong>
            </div>
            <div className="view-tabs" role="group" aria-label="Calendar view">
              {(["day", "week", "month", "agenda"] as ViewMode[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={view === mode}
                  onClick={() => setView(mode)}
                >
                  {mode[0].toUpperCase() + mode.slice(1)}
                </button>
              ))}
            </div>
            <div className="row">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status filter">
                <option value="active">Active</option>
                <option value="all">All statuses</option>
                <option value="booked">Booked</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <select
                value={serviceFilter}
                onChange={(e) => setServiceFilter(e.target.value)}
                aria-label="Service filter"
              >
                <option value="">All services</option>
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  setDrawerMode("create");
                  setSelected(null);
                  setLocalStart(nowClinicLocalInput(clinicTimezone));
                }}
              >
                Create appointment
              </button>
              <button type="button" className="secondary" onClick={() => setDrawerMode("hours")}>
                Opening hours
              </button>
            </div>
          </div>

          {view === "agenda" ? (
            <ul className="agenda-list">
              {filtered.length === 0 ? (
                <li className="meta">No appointments match these filters.</li>
              ) : (
                filtered
                  .slice()
                  .sort((a, b) => a.starts_at_utc.localeCompare(b.starts_at_utc))
                  .map((row) => (
                    <li key={row.id}>
                      <button
                        type="button"
                        className="text-link"
                        onClick={() => {
                          setSelected(row);
                          setDrawerMode("detail");
                          setRescheduleLocal(utcIsoToClinicLocalInput(row.starts_at_utc, clinicTimezone));
                        }}
                      >
                        {row.starts_at_clinic} · {row.service_name}
                      </button>
                      <p className="meta">
                        {row.customer_name} · {row.status}
                      </p>
                    </li>
                  ))
              )}
            </ul>
          ) : null}

          {view === "month" ? (
            <div className="calendar-grid month">
              {WEEKDAYS.map((d) => (
                <div key={d} className="cal-cell" style={{ minHeight: "auto", fontWeight: 600 }}>
                  {d}
                </div>
              ))}
              {Array.from({ length: 42 }, (_, i) => {
                const day = addDays(monthStart, i);
                const events = eventsByDay.get(dayKey(day)) ?? [];
                return (
                  <div
                    key={dayKey(day)}
                    className={`cal-cell ${day.getMonth() !== cursor.getMonth() ? "muted" : ""} ${sameDay(day, new Date()) ? "today" : ""}`}
                  >
                    <div>{day.getDate()}</div>
                    {events.slice(0, 3).map((ev) => (
                      <button
                        key={ev.id}
                        type="button"
                        className="cal-event"
                        onClick={() => {
                          setSelected(ev);
                          setDrawerMode("detail");
                          setRescheduleLocal(utcIsoToClinicLocalInput(ev.starts_at_utc, clinicTimezone));
                        }}
                      >
                        {ev.service_name}
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          ) : null}

          {view === "week" || view === "day" ? (
            <div className="calendar-grid week" style={view === "day" ? { gridTemplateColumns: "3.5rem 1fr" } : undefined}>
              <div className="cal-cell" style={{ minHeight: "auto" }} />
              {(view === "day" ? [cursor] : Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))).map(
                (day) => (
                  <div
                    key={dayKey(day)}
                    className={`cal-cell ${sameDay(day, new Date()) ? "today" : ""}`}
                    style={{ minHeight: "auto", fontWeight: 600 }}
                  >
                    {day.toLocaleDateString(undefined, { weekday: "short", day: "numeric" })}
                  </div>
                ),
              )}
              {Array.from({ length: 12 }, (_, hour) => {
                const h = hour + 8;
                const days =
                  view === "day" ? [cursor] : Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
                return (
                  <div key={`row-${h}`} style={{ display: "contents" }}>
                    <div className="cal-cell muted" style={{ minHeight: "3.2rem" }}>
                      {`${h.toString().padStart(2, "0")}:00`}
                    </div>
                    {days.map((day) => {
                      const events = (eventsByDay.get(dayKey(day)) ?? []).filter((ev) => {
                        return clinicHour(new Date(ev.starts_at_utc), clinicTimezone) === h;
                      });
                      return (
                        <div key={`${dayKey(day)}-${h}`} className="cal-cell" style={{ minHeight: "3.2rem" }}>
                          {events.map((ev) => (
                            <button
                              key={ev.id}
                              type="button"
                              className="cal-event"
                              onClick={() => {
                                setSelected(ev);
                                setDrawerMode("detail");
                                setRescheduleLocal(utcIsoToClinicLocalInput(ev.starts_at_utc, clinicTimezone));
                              }}
                            >
                              {ev.customer_name}
                            </button>
                          ))}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>

        {drawerMode ? (
          <aside className="drawer" aria-label="Appointment details">
            {drawerMode === "detail" && selected ? (
              <>
                <h2>{selected.service_name}</h2>
                <p className="meta">
                  {selected.customer_name} · {selected.status}
                </p>
                <p>
                  <strong>{selected.starts_at_clinic}</strong>
                  <br />
                  <span className="meta">Ends {selected.ends_at_clinic} · {clinicTimezone}</span>
                </p>
                <p className="meta">
                  {selected.provider === "calcom"
                    ? selected.sync_status === "synced"
                      ? `On Clinic Dial and Cal.com${selected.external_event_id ? ` · ${selected.external_event_id}` : ""}. Cal.com emails the customer.`
                      : `On Clinic Dial · Cal.com sync: ${selected.sync_status || "pending"}`
                    : selected.provider === "google"
                      ? `On Clinic Dial · Google sync: ${selected.sync_status || "local"}`
                      : "Saved in Clinic Dial. Connect Cal.com or Google under Integrations to sync outward."}
                </p>
                {selected.status !== "cancelled" ? (
                  <>
                    <form className="stack" onSubmit={onReschedule}>
                      <label>
                        New start ({clinicTimezone})
                        <input
                          type="datetime-local"
                          required
                          value={rescheduleLocal}
                          onChange={(e) => setRescheduleLocal(e.target.value)}
                        />
                      </label>
                      <button type="submit" disabled={busy}>
                        Save new time
                      </button>
                    </form>
                    <button
                      type="button"
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        const ok = window.confirm(
                          `Cancel this appointment for ${selected.customer_name}? The time slot becomes available again.`,
                        );
                        if (ok) void onCancel();
                      }}
                    >
                      Cancel appointment
                    </button>
                  </>
                ) : null}
                <button type="button" className="ghost" onClick={() => setDrawerMode(null)}>
                  Close details
                </button>
              </>
            ) : null}

            {drawerMode === "create" ? (
              <>
                <h2>Create appointment</h2>
                <form className="stack" onSubmit={onBook}>
                  <label>
                    Patient
                    <select required value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                      {customers.length === 0 ? <option value="">No patients yet</option> : null}
                      {customers.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.full_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Service
                    <select required value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
                      {services.length === 0 ? <option value="">Add a bookable service first</option> : null}
                      {services.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({s.duration_minutes}m)
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
                    Create appointment
                  </button>
                </form>
                <button type="button" className="ghost" onClick={() => setDrawerMode(null)}>
                  Close
                </button>
              </>
            ) : null}

            {drawerMode === "hours" ? (
              <>
                <h2>Opening hours</h2>
                <p className="meta">
                  Enter times in your clinic timezone ({clinicTimezone}). Visitors can book only after hours are set.
                </p>
                <form className="stack" onSubmit={onAddHours}>
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
                    Opens
                    <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} required />
                  </label>
                  <label>
                    Closes
                    <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} required />
                  </label>
                  <button type="submit" disabled={busy}>
                    Add opening hours
                  </button>
                </form>
                {windows.length === 0 ? (
                  <p className="meta">No opening hours yet. Public booking stays closed until you add them.</p>
                ) : (
                  <ul className="data-list">
                    {windows.map((row) => (
                      <li key={row.id}>
                        <strong>{WEEKDAYS[row.weekday]}</strong>
                        <p className="meta">
                          {timeFromMinutes(row.start_minute)}–{timeFromMinutes(row.end_minute)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
                <button type="button" className="ghost" onClick={() => setDrawerMode(null)}>
                  Close
                </button>
              </>
            ) : null}
          </aside>
        ) : null}
      </div>
    </div>
  );
}
