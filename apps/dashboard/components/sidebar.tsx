"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const GROUPS: {
  label: string;
  items: { href: string; label: string; icon: string }[];
}[] = [
  {
    label: "Workspace",
    items: [
      { href: "/overview", label: "Overview", icon: "◇" },
      { href: "/calendar", label: "Calendar", icon: "▦" },
      { href: "/enquiries", label: "Enquiries", icon: "✉" },
      { href: "/patients", label: "Patients", icon: "☺" },
    ],
  },
  {
    label: "AI receptionist",
    items: [
      { href: "/conversations", label: "Conversations", icon: "◎" },
      { href: "/handovers", label: "Handovers", icon: "⚑" },
      { href: "/receptionist", label: "Receptionist", icon: "◉" },
    ],
  },
  {
    label: "Clinic",
    items: [
      { href: "/services", label: "Services", icon: "☰" },
      { href: "/website", label: "Website", icon: "⌂" },
      { href: "/integrations", label: "Integrations", icon: "⇄" },
      { href: "/settings", label: "Settings", icon: "⚙" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { me, busy, signOut } = useAuth();
  const clinic = me?.clinic;

  return (
    <aside className="sidebar" aria-label="Clinic workspace">
      <div className="sidebar-clinic">
        <p className="sidebar-brand">Clinic Dial</p>
        <h2 className="sidebar-clinic-name">{clinic?.name ?? "Clinic"}</h2>
        <p className="sidebar-clinic-meta">
          {clinic?.timezone ?? "Timezone not set"}
          {me?.membership?.role ? ` · ${me.membership.role}` : ""}
        </p>
      </div>

      {GROUPS.map((group) => (
        <nav key={group.label} className="nav-group" aria-label={group.label}>
          <p className="nav-group-label">{group.label}</p>
          {group.items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className="nav-item"
                aria-current={active ? "page" : undefined}
              >
                <span className="nav-icon" aria-hidden>
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </nav>
      ))}

      <div className="sidebar-footer">
        <Link href="/onboarding" className="nav-item">
          <span className="nav-icon" aria-hidden>
            →
          </span>
          Setup checklist
        </Link>
        <button type="button" className="ghost" disabled={busy} onClick={() => void signOut()}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
