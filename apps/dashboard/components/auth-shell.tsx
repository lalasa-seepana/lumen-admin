"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthFrame } from "@/components/auth-frame";
import { useAuth } from "@/lib/auth-context";

type Mode = "signin" | "signup" | "forgot" | "update";

export function AuthShell() {
  const router = useRouter();
  const {
    ready,
    accessToken,
    me,
    busy,
    error,
    notice,
    setError,
    setNotice,
    signIn,
    signUp,
    forgotPassword,
    updatePassword,
    createClinicProfile,
    signOut,
  } = useAuth();

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [clinicName, setClinicName] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");

  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hash.includes("type=recovery")) {
      setMode("update");
      setNotice("Choose a new password for your account.");
    }
  }, [setNotice]);

  useEffect(() => {
    if (ready && accessToken && me?.clinic) {
      router.replace("/overview");
    }
  }, [ready, accessToken, me, router]);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    if (next !== "forgot") setNotice(null);
  }

  async function onAuth(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      if (mode === "signup") await signUp(email, password);
      else await signIn(email, password);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed. Please try again.");
    }
  }

  async function onForgot(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await forgotPassword(email);
      setMode("signin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not send a reset email. Try again in a moment.");
    }
  }

  async function onUpdatePassword(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await updatePassword(password);
      setPassword("");
      setMode("signin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not update your password. Try again.");
    }
  }

  async function onCreateClinic(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await createClinicProfile({ name: clinicName, timezone });
      router.replace("/onboarding");
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not create your clinic. Try again.");
    }
  }

  if (!ready) {
    return (
      <AuthFrame lede="Checking your session…" busy>
        <p className="meta">This only takes a moment.</p>
      </AuthFrame>
    );
  }

  if (mode === "update") {
    return (
      <AuthFrame lede="Choose a new password to return to your clinic.">
        <section className="panel stack" aria-labelledby="auth-panel-title">
          <div>
            <h2 id="auth-panel-title" className="panel-title">
              New password
            </h2>
            <p className="panel-hint">Use at least 8 characters.</p>
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
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Saving password…" : "Save password"}
            </button>
          </form>
          <p className="mode-switch">
            <button type="button" disabled={busy} onClick={() => switchMode("signin")}>
              Back to sign in
            </button>
          </p>
          {notice ? <p className="notice">{notice}</p> : null}
          {error ? <p className="error">{error}</p> : null}
        </section>
      </AuthFrame>
    );
  }

  if (!accessToken || !me) {
    if (mode === "forgot") {
      return (
        <AuthFrame lede="Enter your email and we will send a link to set a new password.">
          <section className="panel stack" aria-labelledby="auth-panel-title">
            <div>
              <h2 id="auth-panel-title" className="panel-title">
                Reset password
              </h2>
              <p className="panel-hint">Use the email for your clinic owner account.</p>
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
                {busy ? "Sending link…" : "Send reset link"}
              </button>
            </form>
            <p className="mode-switch">
              Remembered it?{" "}
              <button type="button" disabled={busy} onClick={() => switchMode("signin")}>
                Sign in
              </button>
            </p>
            {error ? <p className="error">{error}</p> : null}
          </section>
        </AuthFrame>
      );
    }

    const isSignup = mode === "signup";
    return (
      <AuthFrame lede="Manage appointments, enquiries, and your AI receptionist.">
        <section className="panel stack" aria-labelledby="auth-panel-title">
          <div>
            <h2 id="auth-panel-title" className="panel-title">
              {isSignup ? "Create account" : "Sign in"}
            </h2>
            <p className="panel-hint">
              {isSignup
                ? "Use the email you will manage this clinic with."
                : "For clinic owners. Each account keeps its own clinic data private."}
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
            </label>
            {!isSignup ? (
              <p className="field-actions">
                <button type="button" className="text-link" disabled={busy} onClick={() => switchMode("forgot")}>
                  Forgot password?
                </button>
              </p>
            ) : null}
            <button type="submit" disabled={busy}>
              {busy ? (isSignup ? "Creating account…" : "Signing in…") : isSignup ? "Create account" : "Sign in"}
            </button>
          </form>
          <p className="mode-switch">
            {isSignup ? "Already have an account?" : "Need an account?"}{" "}
            <button type="button" disabled={busy} onClick={() => switchMode(isSignup ? "signin" : "signup")}>
              {isSignup ? "Sign in" : "Sign up"}
            </button>
          </p>
          {notice ? <p className="notice">{notice}</p> : null}
          {error ? <p className="error">{error}</p> : null}
        </section>
      </AuthFrame>
    );
  }

  if (!me.clinic) {
    return (
      <AuthFrame lede="Add your clinic name to open your workspace.">
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
                placeholder="Andaman Wellness"
              />
            </label>
            <label>
              Timezone
              <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                <option value="Asia/Kolkata">Asia/Kolkata</option>
                <option value="Asia/Bangkok">Asia/Bangkok</option>
                <option value="Asia/Dubai">Asia/Dubai</option>
                <option value="Europe/London">Europe/London</option>
                <option value="America/New_York">America/New_York</option>
              </select>
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Creating clinic…" : "Create clinic"}
            </button>
          </form>
          <p className="mode-switch">
            <button type="button" disabled={busy} onClick={() => void signOut()}>
              Sign out
            </button>
          </p>
          {error ? <p className="error">{error}</p> : null}
        </section>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame lede="Opening your workspace…" busy>
      <p className="meta">Taking you to Overview.</p>
    </AuthFrame>
  );
}
