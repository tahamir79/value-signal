import type { Metadata } from "next";
import { BillingPlans } from "@/components/BillingPlans";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { entitlementForUser } from "@/lib/billing-store";
import { getCurrentSession } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Billing" };
export const dynamic = "force-dynamic";

export default async function BillingPage() {
  const session = await getCurrentSession();
  const entitlement = await entitlementForUser(session?.user?.id);
  const annualConfigured = Boolean(process.env.STRIPE_VALUE_SIGNAL_ANNUAL_PRICE_ID);

  return (
    <div className="page billing-page">
      <header className="page-head split">
        <div>
          <p className="eyebrow">VALUESIGNAL PRO / BILLING</p>
          <h1>Unlock the full research universe.</h1>
          <p>Google sign-in gives a free preview expansion. Pro unlocks the full scaled universe and premium research views.</p>
        </div>
        <div className="as-of">
          <span>ACCESS</span>
          <strong>{entitlement.isPro ? "PRO" : entitlement.isAuthenticated ? "FREE" : "PUBLIC"}</strong>
        </div>
      </header>
      <Disclaimer />
      <section className="billing-summary">
        <article>
          <p className="eyebrow">CURRENT POLICY</p>
          <ul>
            <li>Signed out: original ten-stock public preview.</li>
            <li>Google signed-in free: preview plus up to three undervalued and three Growth Spurt/emerging candidates.</li>
            <li>ValueSignal Pro: full 5,799-company universe and full company detail access.</li>
          </ul>
        </article>
        <article>
          <p className="eyebrow">SUBSCRIPTION STATE</p>
          <dl>
            <div><dt>Plan</dt><dd>{entitlement.subscription?.plan ?? "free"}</dd></div>
            <div><dt>Status</dt><dd>{entitlement.subscription?.status ?? "none"}</dd></div>
            <div><dt>Renews / ends</dt><dd>{entitlement.subscription?.currentPeriodEnd ? new Date(entitlement.subscription.currentPeriodEnd).toLocaleDateString("en-US", { dateStyle: "medium" }) : "Not available"}</dd></div>
          </dl>
        </article>
      </section>
      {!session?.user ? (
        <section className="universe-lock panel-lock">
          <div>
            <p className="eyebrow">SIGN-IN FIRST</p>
            <h2>Use Google before opening Stripe Checkout.</h2>
            <p>Subscriptions are associated with your authenticated ValueSignal account. The client never submits user IDs, Product IDs, or Price IDs.</p>
          </div>
          <GoogleSignInButton label="Log in using Google" callbackURL="/billing" />
        </section>
      ) : entitlement.isPro ? (
        <section className="billing-active">
          <p className="eyebrow">PRO ACTIVE</p>
          <h2>Your account has ValueSignal Pro access.</h2>
          <p>Subscription management will use the Stripe-supported managed-payments path once the Dashboard setup is finalized.</p>
        </section>
      ) : (
        <BillingPlans annualConfigured={annualConfigured} />
      )}
    </div>
  );
}
