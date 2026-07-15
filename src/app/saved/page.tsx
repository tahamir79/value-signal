import type { Metadata } from "next";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { SavedStocksConsole } from "@/components/SavedStocksConsole";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { getCurrentSession } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Saved stocks" };
export const dynamic = "force-dynamic";

export default async function SavedStocksPage() {
  const session = await getCurrentSession();

  if (!session?.user) {
    return (
      <div className="page">
        <header className="page-head">
          <p className="eyebrow">SAVED STOCKS</p>
          <h1>Sign in to organize research</h1>
          <p>Watchlists and Portfolio notes are private to your Google-authenticated account.</p>
        </header>
        <Disclaimer />
        <section className="universe-lock panel-lock">
          <div>
            <p className="eyebrow">GOOGLE SIGN-IN REQUIRED</p>
            <h2>Save Watchlist and Portfolio records securely.</h2>
            <p>ValueSignal uses your authenticated session to save records. The browser never submits or controls a user ID.</p>
          </div>
          <GoogleSignInButton label="Log in using Google" callbackURL="/saved" />
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-head">
        <p className="eyebrow">SAVED STOCKS</p>
        <h1>Watchlist and Portfolio</h1>
        <p>Organize companies for research. Portfolio entries are notes only, not brokerage transactions or advice.</p>
      </header>
      <Disclaimer />
      <SavedStocksConsole />
    </div>
  );
}
