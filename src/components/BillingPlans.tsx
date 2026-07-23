"use client";

import { useState } from "react";

type Interval = "month" | "year";

export function BillingPlans({ annualConfigured }: { annualConfigured: boolean }) {
  const [busy, setBusy] = useState<Interval | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function startCheckout(interval: Interval) {
    setBusy(interval);
    setError(null);
    try {
      const response = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interval }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.url) {
        throw new Error(payload.error || "Checkout is not available yet.");
      }
      window.location.assign(payload.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open Stripe Checkout.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="billing-plans">
      <article>
        <p className="eyebrow">MONTHLY</p>
        <h3>ValueSignal Pro</h3>
        <p>Unlock the full universe, premium candidate filters, and full company-level evidence access.</p>
        <button type="button" onClick={() => void startCheckout("month")} disabled={busy !== null}>
          {busy === "month" ? "Opening Stripe…" : "Subscribe monthly"}
        </button>
      </article>
      <article>
        <p className="eyebrow">YEARLY</p>
        <h3>Annual Pro</h3>
        <p>Use the same Pro access policy with a yearly recurring Stripe Price when configured.</p>
        <button type="button" onClick={() => void startCheckout("year")} disabled={busy !== null || !annualConfigured}>
          {busy === "year" ? "Opening Stripe…" : annualConfigured ? "Subscribe yearly" : "Yearly price not configured"}
        </button>
      </article>
      {error ? <p className="billing-error" role="status">{error}</p> : null}
    </div>
  );
}
