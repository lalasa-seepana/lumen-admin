"use client";

import { FormEvent, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth-context";
import { apiBaseUrl } from "@/lib/supabase";

const STORAGE_KEY = "lala.receptionist.settings";

type Settings = {
  greeting: string;
  language: string;
  approvedKnowledge: string;
};

const DEFAULTS: Settings = {
  greeting: "Hello. I’m Rhea, the clinic’s AI receptionist. How can I help today?",
  language: "en-IN",
  approvedKnowledge: "",
};

export default function ReceptionistPage() {
  const { me } = useAuth();
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceStatus, setVoiceStatus] = useState<string | null>(null);
  const [voiceDetail, setVoiceDetail] = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setSettings({ ...DEFAULTS, ...JSON.parse(raw) });
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`${apiBaseUrl()}/v1/voice/status`);
        const body = await res.json();
        const mode = body?.mode ?? "demo";
        setVoiceStatus(typeof mode === "string" ? mode : "unknown");
        const parts = [
          body?.ready_for_live ? "Ready for live" : "Not live-ready",
          body?.gnani_configured ? "Gnani configured" : "Gnani missing",
          body?.llm_configured ? "LLM configured" : "LLM missing",
        ];
        if (Array.isArray(body?.blockers) && body.blockers.length) {
          parts.push(`Blockers: ${body.blockers.slice(0, 2).join("; ")}`);
        }
        setVoiceDetail(parts.join(" · "));
      } catch {
        setVoiceStatus("unreachable");
        setVoiceDetail(null);
      }
    })();
  }, []);

  function onSave(event: FormEvent) {
    event.preventDefault();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    setNotice(
      "Settings saved on this device. Clinic-wide server settings will sync when onboarding persistence is enabled for your account.",
    );
  }

  const clinicRef = me?.clinic?.public_slug || me?.clinic?.id;
  const visitorUrl = clinicRef
    ? `http://127.0.0.1:3002/?clinic=${encodeURIComponent(clinicRef)}`
    : "http://127.0.0.1:3002/";

  const modeLabel =
    voiceStatus === null
      ? "Checking…"
      : voiceStatus === "demo" || voiceStatus === "mock"
        ? "Demo mode"
        : voiceStatus === "speech_only"
          ? "Speech on (Gnani) · mock brain (no GPU Evon)"
          : voiceStatus === "configured"
            ? "Configured (credentials present — live path not verified here)"
            : voiceStatus === "partial" || voiceStatus === "llm_only"
              ? "Partial (speech or LLM still missing)"
              : voiceStatus === "unreachable"
                ? "API unreachable"
                : voiceStatus;

  return (
    <>
      <PageHeader
        title="Receptionist"
        description="Greeting, language, approved information, and a link to try the visitor experience."
      />
      <div className="page-body">
        {notice ? <p className="notice">{notice}</p> : null}
        <section className="panel stack">
          <p className="meta">
            Voice status:{" "}
            <span
              className={`status-pill status-${
                voiceStatus === "demo" ||
                voiceStatus === "mock" ||
                voiceStatus === "unreachable" ||
                voiceStatus === "partial" ||
                voiceStatus === "llm_only"
                  ? "mock"
                  : "accepted"
              }`}
            >
              {modeLabel}
            </span>
          </p>
          {voiceDetail ? <p className="meta">{voiceDetail}</p> : null}
          <form className="stack" onSubmit={onSave}>
            <label>
              Greeting
              <textarea
                rows={3}
                value={settings.greeting}
                onChange={(e) => setSettings((s) => ({ ...s, greeting: e.target.value }))}
              />
            </label>
            <label>
              Default language
              <select
                value={settings.language}
                onChange={(e) => setSettings((s) => ({ ...s, language: e.target.value }))}
              >
                <option value="en-IN">English (India)</option>
                <option value="hi-IN">Hindi</option>
                <option value="te-IN">Telugu</option>
              </select>
            </label>
            <label>
              Approved information
              <textarea
                rows={5}
                placeholder="Only facts you want the receptionist to share with visitors."
                value={settings.approvedKnowledge}
                onChange={(e) => setSettings((s) => ({ ...s, approvedKnowledge: e.target.value }))}
              />
            </label>
            <p className="meta">
              Opening hours live on Calendar. Visitors can book only after hours are set.
            </p>
            <button type="submit">Save changes</button>
          </form>
        </section>
        <section className="panel stack">
          <h2 className="panel-title">Try the visitor experience</h2>
          <p className="panel-hint">
            Opens the visitor page without owner sign-in. Demo mode is labeled when live speech is not configured.
          </p>
          <a className="btn" href={visitorUrl} target="_blank" rel="noreferrer" style={{ textAlign: "center" }}>
            Open visitor receptionist
          </a>
        </section>
      </div>
    </>
  );
}
