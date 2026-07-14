"use client";

import { useState } from "react";
import { authClient } from "@/lib/auth-client";

export function AuthStatus() {
  const { data: session, isPending } = authClient.useSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signInWithGoogle() {
    setBusy(true);
    setError(null);

    try {
      const result = await authClient.signIn.social({ provider: "google", callbackURL: "/rag" });

      if (result?.error) {
        setError(result.error.message || "Google sign-in is not configured yet.");
      }
    } catch {
      setError("Could not reach the auth route. Check the local port and auth environment values.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError(null);

    try {
      const result = await authClient.signOut();
      if (result?.error) {
        setError(result.error.message || "Sign out failed.");
      }
    } catch {
      setError("Could not reach the auth route.");
    } finally {
      setBusy(false);
    }
  }

  if (isPending) {
    return <span className="auth-status" aria-live="polite">Auth…</span>;
  }

  return (
    <div className="auth-wrap">
      {session?.user ? (
        <button className="auth-button" type="button" onClick={() => void signOut()} disabled={busy}>
          Sign out
        </button>
      ) : (
        <button className="google-auth-button" type="button" onClick={() => void signInWithGoogle()} disabled={busy}>
          <span aria-hidden="true" className="google-g">G</span>
          <span>{busy ? "Opening Google…" : "Sign in with Google"}</span>
        </button>
      )}
      {error ? <small className="auth-error" role="status">{error}</small> : null}
    </div>
  );
}
