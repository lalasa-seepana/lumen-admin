"use client";

import { FormEvent, useEffect, useState } from "react";
import { AuthFrame } from "@/components/auth-frame";
import { createClinic, fetchMe } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import type { MeResponse } from "@/lib/types";

type Mode = "signin" | "signup" | "forgot" | "update";

export function AuthShell() {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [clinicName, setClinicName] = useState("");
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const supabase = getSupabase();

    const { data: authListener } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (cancelled) return;
      if (event === "PASSWORD_RECOVERY") {
        setMode("update");
        setAccessToken(session?.access_token ?? null);
        setError(null);
        setNotice("Choose a new password for your Lala account.");
        setReady(true);
        return;
      }
      if (event === "SIGNED_OUT") {
        setAccessToken(null);
        setMe(null);
      }
    });

    (async () => {
      try {
        const { data } = await supabase.auth.getSession();
        const token = data.session?.access_token ?? null;
        if (cancelled) return;

        // Recovery links land with a session before PASSWORD_RECOVERY may fire.
        if (typeof window !== "undefined" && window.location.hash.includes("type=recovery")) {
          setMode("update");
          setAccessToken(token);
          setNotice("Choose a new password for your Lala account.");
          return;
        }

        setAccessToken(token);
        if (token) {
          try {
            const profile = await fetchMe(token);
            if (!cancelled) setMe(profile);
          } catch (err) {
            await supabase.auth.signOut();
            if (!cancelled) {
              setAccessToken(null);
              setMe(null);
              setError(
                err instanceof Error
                  ? `${err.message}. Signed out — please sign in again.`
                  : "Session was invalid. Please sign in again.",
              );
            }
          }
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to restore session");
      } finally {
        if (!cancelled) setReady(true);
      }
    })();

    return () => {
      cancelled = true;
      authListener.subscription.unsubscribe();
    };
  }, []);

  async function onAuth(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const supabase = getSupabase();
      const result =
        mode === "signup"
          ? await supabase.auth.signUp({ email, password })
          : await supabase.auth.signInWithPassword({ email, password });
      if (result.error) throw result.error;
      const token = result.data.session?.access_token;
      if (!token) {
        throw new Error(
          mode === "signup"
            ? "Account created. Confirm your email if required, then sign in."
            : "No session returned",
        );
      }
      setAccessToken(token);
      setMe(await fetchMe(token));
      setPassword("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed";
      setError(
        mode === "signin" && /invalid login credentials/i.test(message)
          ? "Invalid email or password. Try again, or use Forgot password."
          : message,
      );
    } finally {
      setBusy(false);
    }
  }

  async function onForgot(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const redirectTo = `${window.location.origin}/`;
      const { error: resetError } = await getSupabase().auth.resetPasswordForEmail(email.trim(), {
        redirectTo,
      });
      if (resetError) throw resetError;
      setNotice(`If an account exists for ${email.trim()}, a reset link is on its way. Check your inbox.`);
      setMode("signin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send reset email");
    } finally {
      setBusy(false);
    }
  }

  async function onUpdatePassword(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { data, error: updateError } = await getSupabase().auth.updateUser({ password });
      if (updateError) throw updateError;
      const token = (await getSupabase().auth.getSession()).data.session?.access_token;
      if (!token) throw new Error("Password updated, but no session was returned. Please sign in.");
      setAccessToken(token);
      setMe(await fetchMe(token));
      setPassword("");
      setMode("signin");
      setNotice("Password updated.");
      // Clear recovery hash from the URL without a full reload.
      if (typeof window !== "undefined" && window.location.hash) {
        window.history.replaceState(null, "", window.location.pathname);
      }
      void data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update password");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateClinic(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setBusy(true);
    setError(null);
    try {
      const profile = await createClinic(accessToken, { name: clinicName });
      setMe(profile);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create clinic");
    } finally {
      setBusy(false);
    }
  }

  async function onSignOut() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await getSupabase().auth.signOut();
      setAccessToken(null);
      setMe(null);
      setMode("signin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign out failed");
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    if (next !== "forgot") setNotice(null);
  }

  if (!ready) {
    return (
      <AuthFrame lede="Loading your session…" busy>
        <p className="meta">Restoring your clinic session.</p>
      </AuthFrame>
    );
  }

  if (mode === "update") {
    return (
      <AuthFrame lede="Set a new password to get back into your clinic.">
        <section className="panel stack" aria-labelledby="auth-panel-title">
          <div>
            <h2 id="auth-panel-title" className="panel-title">
              New password
            </h2>
            <p className="panel-hint">Use at least 8 characters. You’ll stay signed in after saving.</p>
          </div>
          <form className="stack" onSubmit={onUpdatePassword}>
            <label>
              New password
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="field-hint">Minimum 8 characters</p>
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save password"}
            </button>
          </form>
          <p className="mode-switch">
            <button type="button" disabled={busy} onClick={() => switchMode("signin")}>
              Back to sign in
            </button>
          </p>
          {notice ? (
            <p className="notice" role="status" aria-live="polite">
              {notice}
            </p>
          ) : null}
          {error ? (
            <p className="error" role="alert" aria-live="assertive">
              {error}
            </p>
          ) : null}
        </section>
      </AuthFrame>
    );
  }

  if (!accessToken || !me) {
    const isSignup = mode === "signup";
    const isForgot = mode === "forgot";

    if (isForgot) {
      return (
        <AuthFrame lede="We’ll email a link so you can choose a new password.">
          <section className="panel stack" aria-labelledby="auth-panel-title">
            <div>
              <h2 id="auth-panel-title" className="panel-title">
                Forgot password
              </h2>
              <p className="panel-hint">Enter the email you use for this clinic owner account.</p>
            </div>
            <form className="stack" onSubmit={onForgot}>
              <label>
                Email
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <button type="submit" disabled={busy}>
                {busy ? "Sending…" : "Send reset link"}
              </button>
            </form>
            <p className="mode-switch">
              Remembered it?{" "}
              <button type="button" disabled={busy} onClick={() => switchMode("signin")}>
                Sign in
              </button>
            </p>
            {error ? (
              <p className="error" role="alert" aria-live="assertive">
                {error}
              </p>
            ) : null}
          </section>
        </AuthFrame>
      );
    }

    return (
      <AuthFrame lede="Sign in to manage your clinic’s enquiries, customers, and operations.">
        <section className="panel stack" aria-labelledby="auth-panel-title">
          <div>
            <h2 id="auth-panel-title" className="panel-title">
              {isSignup ? "Create account" : "Sign in"}
            </h2>
            <p className="panel-hint">
              {isSignup
                ? "Use the email you’ll manage this clinic with. Password must be at least 8 characters."
                : "Clinic owners only — each account stays on its own tenant."}
            </p>
          </div>
          <form className="stack" onSubmit={onAuth}>
            <label>
              Email
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {isSignup ? <p className="field-hint">Minimum 8 characters</p> : null}
            </label>
            {!isSignup ? (
              <p className="field-actions">
                <button type="button" className="text-link" disabled={busy} onClick={() => switchMode("forgot")}>
                  Forgot password?
                </button>
              </p>
            ) : null}
            <button type="submit" disabled={busy}>
              {busy ? (isSignup ? "Creating…" : "Signing in…") : isSignup ? "Create account" : "Sign in"}
            </button>
          </form>
          <p className="mode-switch">
            {isSignup ? "Already have an account?" : "Need an account?"}{" "}
            <button
              type="button"
              disabled={busy}
              onClick={() => switchMode(isSignup ? "signin" : "signup")}
            >
              {isSignup ? "Sign in" : "Sign up"}
            </button>
          </p>
          {notice ? (
            <p className="notice" role="status" aria-live="polite">
              {notice}
            </p>
          ) : null}
          {error ? (
            <p className="error" role="alert" aria-live="assertive">
              {error}
            </p>
          ) : null}
        </section>
      </AuthFrame>
    );
  }

  if (!me.clinic) {
    return (
      <AuthFrame
        lede="Name your clinic to finish onboarding. Timezone defaults to Asia/Kolkata."
        brandHeadline="Your clinic identity starts here."
        brandSupport="Create a tenant with its own customers and enquiries — never mixed with another clinic."
      >
        <section className="panel stack" aria-labelledby="onboard-panel-title">
          <div>
            <h2 id="onboard-panel-title" className="panel-title">
              Create your clinic
            </h2>
            <p className="panel-hint">Signed in as {me.email ?? me.user_id}</p>
          </div>
          <form className="stack" onSubmit={onCreateClinic}>
            <label>
              Clinic name
              <input
                required
                minLength={2}
                maxLength={120}
                value={clinicName}
                onChange={(e) => setClinicName(e.target.value)}
                placeholder="Demo Clinic A"
              />
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Creating…" : "Create clinic"}
            </button>
          </form>
          <p className="mode-switch">
            <button type="button" disabled={busy} onClick={onSignOut}>
              Sign out
            </button>
          </p>
          {notice ? (
            <p className="notice" role="status" aria-live="polite">
              {notice}
            </p>
          ) : null}
          {error ? (
            <p className="error" role="alert" aria-live="assertive">
              {error}
            </p>
          ) : null}
        </section>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame
      lede="Your clinic workspace is ready. CRM modules arrive in Epic 4."
      brandHeadline={`${me.clinic.name} is on Lala.`}
      brandSupport="Owner tools for enquiries and customers come next — still one isolated tenant."
    >
      <section className="panel stack" aria-labelledby="workspace-title">
        <p className="meta">Signed in as {me.email ?? me.user_id}</p>
        <h2 id="workspace-title" className="clinic-name">
          {me.clinic.name}
        </h2>
        <p className="meta">
          Role {me.membership?.role ?? "owner"} · Timezone {me.clinic.timezone}
        </p>
        <div className="row">
          <button type="button" className="secondary" disabled={busy} onClick={onSignOut}>
            Sign out
          </button>
        </div>
        {notice ? (
          <p className="notice" role="status" aria-live="polite">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p className="error" role="alert" aria-live="assertive">
            {error}
          </p>
        ) : null}
      </section>
    </AuthFrame>
  );
}
