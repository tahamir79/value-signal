"use client";

import { authClient } from "@/lib/auth-client";

export function AuthStatus() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) {
    return <span className="auth-status" aria-live="polite">Auth…</span>;
  }

  if (session?.user) {
    return (
      <button className="auth-button" type="button" onClick={() => void authClient.signOut()}>
        Sign out
      </button>
    );
  }

  return (
    <button
      className="auth-button"
      type="button"
      onClick={() => void authClient.signIn.social({ provider: "google", callbackURL: "/rag" })}
    >
      Google sign-in
    </button>
  );
}

