"use client";

import { useState } from "react";
import { authClient } from "@/lib/auth-client";

export function GoogleSignInButton({ label = "Sign in with Google", callbackURL = "/dashboard" }: { label?: string; callbackURL?: string }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signInWithGoogle() {
    setBusy(true);
    setError(null);

    try {
      const result = await authClient.signIn.social({ provider: "google", callbackURL });
      if (result?.error) setError(result.error.message || "Google sign-in is not configured yet.");
    } catch {
      setError("Could not reach Google sign-in. Check the auth configuration and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="google-auth-control">
      <button className="google-auth-button" type="button" onClick={() => void signInWithGoogle()} disabled={busy}>
        <span aria-hidden="true" className="google-g">G</span>
        <span>{busy ? "Opening Google…" : label}</span>
      </button>
      {error ? <small className="auth-error" role="status">{error}</small> : null}
    </span>
  );
}
