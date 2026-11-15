"use client";

import { Suspense } from "react";
import { PageHeader } from "@/components/page-header";
import { CalendarWorkspace } from "@/components/calendar-workspace";
import { useAuth } from "@/lib/auth-context";

function CalendarInner() {
  const { accessToken, me } = useAuth();
  if (!accessToken || !me?.clinic) return <p className="meta">Loading calendar…</p>;
  return <CalendarWorkspace accessToken={accessToken} clinicTimezone={me.clinic.timezone} />;
}

export default function CalendarPage() {
  return (
    <>
      <PageHeader
        title="Calendar"
        description="View appointments, create new ones, and set opening hours in your clinic timezone."
      />
      <div className="page-body">
        <Suspense fallback={<p className="meta">Loading calendar…</p>}>
          <CalendarInner />
        </Suspense>
      </div>
    </>
  );
}
