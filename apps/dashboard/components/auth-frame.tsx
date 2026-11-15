import type { ReactNode } from "react";

type AuthFrameProps = {
  children: ReactNode;
  lede: string;
  busy?: boolean;
};

export function AuthFrame({ children, lede, busy }: AuthFrameProps) {
  return (
    <main className="auth-layout" aria-busy={busy || undefined}>
      <div className="auth-card">
        <h1 className="auth-brand">
          Clinic Dial<em>.</em>
        </h1>
        <p className="lede">{lede}</p>
        {children}
      </div>
    </main>
  );
}
