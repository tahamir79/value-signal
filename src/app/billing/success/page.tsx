import Link from "next/link";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";

export default function BillingSuccessPage() {
  return (
    <div className="page">
      <section className="detail-empty">
        <p className="eyebrow">CHECKOUT RETURNED</p>
        <h2>Stripe checkout finished.</h2>
        <p>ValueSignal waits for a verified Stripe webhook before granting Pro access. If your payment completed, refresh after the webhook is processed.</p>
        <Link className="button" href="/billing">Review billing status</Link>
      </section>
      <Disclaimer />
    </div>
  );
}
