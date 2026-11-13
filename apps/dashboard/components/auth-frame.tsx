import type { ReactNode } from "react";
import { BrandAd } from "@/components/brand-ad";

type AuthFrameProps = {
  children: ReactNode;
  lede: string;
  brandHeadline?: string;
  brandSupport?: string;
  busy?: boolean;
};

export function AuthFrame({
  children,
  lede,
  brandHeadline,
  brandSupport,
  busy,
}: AuthFrameProps) {
  return (
    <main className="auth-layout" aria-busy={busy || undefined}>
      <BrandAd headline={brandHeadline} support={brandSupport} />
      <div className="auth-column">
        <h1 className="brand auth-column-brand">Lala</h1>
        <p className="lede">{lede}</p>
        {children}
      </div>
    </main>
  );
}
