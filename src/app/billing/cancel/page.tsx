import Link from "next/link";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";

export default function BillingCancelPage() {
  return (
    <div className="page">
      <section className="detail-empty">
        <p className="eyebrow">CHECKOUT CANCELED</p>
        <h2>No subscription change was made.</h2>
        <p>You can return to billing when you want to start a ValueSignal Pro subscription.</p>
        <Link className="button" href="/billing">Back to billing</Link>
      </section>
      <Disclaimer />
    </div>
  );
}
