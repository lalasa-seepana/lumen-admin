"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import { fetchWebsiteKnowledge, startWebsiteImport } from "@/lib/api";
import type { WebsiteKnowledge } from "@/lib/types";

export default function WebsitePage() {
  const { accessToken } = useAuth();
  const [url, setUrl] = useState("");
  const [knowledge, setKnowledge] = useState<WebsiteKnowledge | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    try {
      setKnowledge(await fetchWebsiteKnowledge(accessToken));
      setError(null);
      setLoadFailed(false);
    } catch (err) {
      setKnowledge(null);
      setLoadFailed(true);
      setError(
        err instanceof Error
          ? err.message
          : "We could not load website knowledge. Refresh to try again.",
      );
    }
  }, [accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onImport(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await startWebsiteImport(accessToken, { url });
      setNotice(
        `Import finished: ${result.drafts_created} draft service${result.drafts_created === 1 ? "" : "s"} from ${result.pages_fetched} page${result.pages_fetched === 1 ? "" : "s"}. Review them under Services.`,
      );
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Import failed. Check the URL is a public website and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Website"
        description="Import public clinic pages into drafts. This is separate from enquiry forwarding and calendar access."
      />
      <div className="page-body">
        {error ? <p className="error">{error}</p> : null}
        {notice ? <p className="notice">{notice}</p> : null}

        <section className="panel stack">
          <h2 className="panel-title">Import website information</h2>
          <p className="panel-hint">
            Clinic Dial reads public pages as untrusted content, not as instructions. Only public http and https addresses are allowed.
          </p>
          <form className="stack" onSubmit={onImport}>
            <label>
              Website URL
              <input
                type="url"
                required
                placeholder="https://example-clinic.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Importing…" : "Import and create drafts"}
            </button>
          </form>
        </section>

        <section className="panel stack">
          <h2 className="panel-title">Imported site</h2>
          {loadFailed && !knowledge ? (
            <div className="empty-state">
              <strong>Could not load website status</strong>
              Refresh this page, or continue setup from the checklist.
            </div>
          ) : !knowledge ? (
            <div className="empty-state">
              <strong>No website imported yet</strong>
              Enter your clinic URL above, or continue from Setup.
            </div>
          ) : (
            <>
              <p>
                <strong>{knowledge.website_url ?? "URL not saved"}</strong>
              </p>
              <p className="meta">
                Last import:{" "}
                {knowledge.last_import_at
                  ? new Date(knowledge.last_import_at).toLocaleString()
                  : "Never"}
                {knowledge.last_error ? ` · Last error: ${knowledge.last_error}` : ""}
              </p>
              <p className="meta">
                Source pages: {knowledge.pages?.length ?? 0} · Pending drafts: {knowledge.pending_drafts}
              </p>
              {knowledge.pages?.length ? (
                <ul className="data-list">
                  {knowledge.pages.map((page) => (
                    <li key={page.url}>
                      <strong>{page.title || page.url}</strong>
                      <p className="meta">
                        {page.url} · {new Date(page.fetched_at).toLocaleString()}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}
        </section>

        <section className="panel stack">
          <h2 className="panel-title">Related setup</h2>
          <ul className="data-list">
            <li>
              <Link href="/integrations">Enquiry forwarding</Link>
              <p className="meta">
                API keys for website forms. Status shows Connected only after a successful submission is verified.
              </p>
            </li>
            <li>
              <Link href="/integrations">Calendar providers</Link>
              <p className="meta">Google Calendar authorization is managed under Integrations.</p>
            </li>
            <li>
              <Link href="/services">Review services</Link>
              <p className="meta">Approve draft services before visitors can book them.</p>
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
