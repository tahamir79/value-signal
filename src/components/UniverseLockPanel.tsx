import Link from "next/link";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";

export function UniverseLockPanel({ ticker }: { ticker?: string }) {
  const normalized = ticker?.toUpperCase();

  return (
    <section className="universe-lock panel-lock" aria-labelledby="universe-lock-heading">
      <div>
        <p className="eyebrow">GOOGLE SIGN-IN REQUIRED</p>
        <h2 id="universe-lock-heading">{normalized ? `${normalized} is in the full ValueSignal universe.` : "The full ValueSignal universe is locked."}</h2>
        <p>The original ten-stock preview remains public. Sign in with Google to access the scaled universe, company-level evidence pages, filing search, and full dashboard screening.</p>
        <Link className="text-link" href="/dashboard">Back to public preview</Link>
      </div>
      <GoogleSignInButton label="Log in using Google" callbackURL={normalized ? `/stock/${normalized}` : "/dashboard"} />
    </section>
  );
}
