import Link from "next/link";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";

export function UniverseLockPanel({ ticker, mode = "signin" }: { ticker?: string; mode?: "signin" | "pro" }) {
  const normalized = ticker?.toUpperCase();
  const needsPro = mode === "pro";

  return (
    <section className="universe-lock panel-lock" aria-labelledby="universe-lock-heading">
      <div>
        <p className="eyebrow">{needsPro ? "VALUESIGNAL PRO REQUIRED" : "GOOGLE SIGN-IN REQUIRED"}</p>
        <h2 id="universe-lock-heading">{normalized ? `${normalized} is in a locked ValueSignal tier.` : "This ValueSignal tier is locked."}</h2>
        <p>{needsPro ? "Your free account includes a limited candidate preview. ValueSignal Pro unlocks the full scaled universe, company-level evidence pages, filing search, and full dashboard screening." : "The original ten-stock preview remains public. Sign in with Google to preview a limited set of additional candidates."}</p>
        <Link className="text-link" href="/dashboard">Back to public preview</Link>
      </div>
      {needsPro ? <Link className="button" href="/billing">Upgrade to Pro</Link> : <GoogleSignInButton label="Log in using Google" callbackURL={normalized ? `/stock/${normalized}` : "/dashboard"} />}
    </section>
  );
}
