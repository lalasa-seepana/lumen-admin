"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { useAuth } from "@/lib/auth-context";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { ready, accessToken, me } = useAuth();

  useEffect(() => {
    if (!ready) return;
    if (!accessToken || !me) {
      router.replace("/");
      return;
    }
    if (!me.clinic) {
      router.replace("/");
    }
  }, [ready, accessToken, me, router]);

  if (!ready || !accessToken || !me?.clinic) {
    return (
      <main className="auth-layout">
        <p className="meta">Opening your clinic workspace…</p>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">{children}</div>
    </div>
  );
}
