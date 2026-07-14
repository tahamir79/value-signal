"use client";

import { useState } from "react";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { authClient } from "@/lib/auth-client";

export function AuthStatus() {
  const { data: session, isPending } = authClient.useSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    setError(null);

    try {
      const result = await authClient.signOut();
      if (result?.error) setError(result.error.message || "Sign out failed.");
    } catch {
      setError("Could not reach the auth route.");
    } finally {
      setBusy(false);
    }
  }

  if (isPending) return <span className="auth-status" aria-live="polite">Auth…</span>;

  if (!session?.user) {
    return (
      <div className="auth-wrap">
        <GoogleSignInButton label="Sign in with Google" callbackURL="/dashboard" />
      </div>
    );
  }

  return (
    <div className="auth-wrap signed-in">
      {session.user.image ? <img className="auth-avatar" src={session.user.image} alt="" referrerPolicy="no-referrer" /> : <span className="auth-avatar fallback" aria-hidden="true">{session.user.name?.charAt(0) ?? "U"}</span>}
      <button className="auth-button" type="button" onClick={() => void signOut()} disabled={busy}>
        Sign out
      </button>
      {error ? <small className="auth-error" role="status">{error}</small> : null}
    </div>
  );
}
