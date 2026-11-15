"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createClinic, fetchMe } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import type { MeResponse } from "@/lib/types";

type AuthContextValue = {
  ready: boolean;
  accessToken: string | null;
  me: MeResponse | null;
  busy: boolean;
  error: string | null;
  notice: string | null;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  refreshMe: () => Promise<MeResponse | null>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  updatePassword: (password: string) => Promise<void>;
  createClinicProfile: (input: { name: string; timezone?: string }) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshMe = useCallback(async () => {
    const supabase = getSupabase();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token ?? null;
    setAccessToken(token);
    if (!token) {
      setMe(null);
      return null;
    }
    const profile = await fetchMe(token);
    setMe(profile);
    return profile;
  }, []);

  useEffect(() => {
    let cancelled = false;
    const supabase = getSupabase();

    const { data: authListener } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (cancelled) return;
      if (event === "SIGNED_OUT") {
        setAccessToken(null);
        setMe(null);
      }
      if (event === "TOKEN_REFRESHED" && session?.access_token) {
        setAccessToken(session.access_token);
      }
    });

    (async () => {
      try {
        await refreshMe();
      } catch (err) {
        await supabase.auth.signOut();
        if (!cancelled) {
          setAccessToken(null);
          setMe(null);
              setError(
                err instanceof Error
                  ? `${err.message}. You have been signed out. Please sign in again.`
                  : "Your session was no longer valid. Please sign in again.",
              );
        }
      } finally {
        if (!cancelled) setReady(true);
      }
    })();

    return () => {
      cancelled = true;
      authListener.subscription.unsubscribe();
    };
  }, [refreshMe]);

  const signIn = useCallback(async (email: string, password: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await getSupabase().auth.signInWithPassword({ email, password });
      if (result.error) throw result.error;
      const token = result.data.session?.access_token;
      if (!token) throw new Error("No session returned");
      setAccessToken(token);
      setMe(await fetchMe(token));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed";
      throw new Error(
        /invalid login credentials/i.test(message)
          ? "That email or password did not match. Try again, or reset your password."
          : message,
      );
    } finally {
      setBusy(false);
    }
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await getSupabase().auth.signUp({ email, password });
      if (result.error) throw result.error;
      const token = result.data.session?.access_token;
      if (!token) {
        throw new Error("Account created. Confirm your email if your project requires it, then sign in.");
      }
      setAccessToken(token);
      setMe(await fetchMe(token));
    } finally {
      setBusy(false);
    }
  }, []);

  const forgotPassword = useCallback(async (email: string) => {
    setBusy(true);
    setError(null);
    try {
      const redirectTo = `${window.location.origin}/`;
      const { error: resetError } = await getSupabase().auth.resetPasswordForEmail(email.trim(), {
        redirectTo,
      });
      if (resetError) throw resetError;
      setNotice(`If an account exists for ${email.trim()}, we sent a reset link to that inbox.`);
    } finally {
      setBusy(false);
    }
  }, []);

  const updatePassword = useCallback(async (password: string) => {
    setBusy(true);
    setError(null);
    try {
      const { error: updateError } = await getSupabase().auth.updateUser({ password });
      if (updateError) throw updateError;
      await refreshMe();
      setNotice("Your password has been updated.");
      if (window.location.hash) {
        window.history.replaceState(null, "", window.location.pathname);
      }
    } finally {
      setBusy(false);
    }
  }, [refreshMe]);

  const createClinicProfile = useCallback(
    async (input: { name: string; timezone?: string }) => {
      if (!accessToken) throw new Error("Not signed in");
      setBusy(true);
      setError(null);
      try {
        const profile = await createClinic(accessToken, input);
        setMe(profile);
      } finally {
        setBusy(false);
      }
    },
    [accessToken],
  );

  const signOut = useCallback(async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await getSupabase().auth.signOut();
      setAccessToken(null);
      setMe(null);
    } finally {
      setBusy(false);
    }
  }, []);

  const value = useMemo(
    () => ({
      ready,
      accessToken,
      me,
      busy,
      error,
      notice,
      setError,
      setNotice,
      refreshMe,
      signIn,
      signUp,
      forgotPassword,
      updatePassword,
      createClinicProfile,
      signOut,
    }),
    [
      ready,
      accessToken,
      me,
      busy,
      error,
      notice,
      refreshMe,
      signIn,
      signUp,
      forgotPassword,
      updatePassword,
      createClinicProfile,
      signOut,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
