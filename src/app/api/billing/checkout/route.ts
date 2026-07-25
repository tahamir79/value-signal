import { NextResponse, type NextRequest } from "next/server";
import { currentStripeLivemode, getUserSubscription } from "@/lib/billing-store";
import { hasProAccess } from "@/lib/billing-policy";
import { getCurrentSession } from "@/lib/server-auth";
import { createValueSignalCheckoutSession, getOrCreateStripeCustomer, missingStripeCheckoutEnv } from "@/lib/stripe-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function error(message: string, status = 400, extra?: Record<string, unknown>) {
  return NextResponse.json({ error: message, ...extra }, { status });
}

export async function POST(request: NextRequest) {
  const session = await getCurrentSession();
  if (!session?.user?.id) return error("Google sign-in is required before starting checkout.", 401);

  const body = await request.json().catch(() => ({}));
  const interval = body?.interval === "year" ? "year" : "month";
  const missing = missingStripeCheckoutEnv(interval);
  if (missing.length) {
    return error("Stripe checkout is not configured yet.", 503, { missing });
  }

  const subscription = await getUserSubscription(session.user.id);
  const stripeLivemode = currentStripeLivemode();
  if (hasProAccess(subscription, new Date(), stripeLivemode)) {
    return error("This account already has ValueSignal Pro access.", 409, { subscription });
  }

  try {
    const stripeCustomerId = await getOrCreateStripeCustomer(
      {
        id: session.user.id,
        email: session.user.email,
        name: session.user.name,
      },
      subscription?.stripeCustomerId,
    );
    const checkout = await createValueSignalCheckoutSession({
      user: {
        id: session.user.id,
        email: session.user.email,
        name: session.user.name,
      },
      stripeCustomerId,
      interval,
    });
    const url = typeof checkout.url === "string" ? checkout.url : null;
    if (!url) return error("Stripe did not return a Checkout URL.", 502);
    return NextResponse.json({ url });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not start Stripe Checkout.", 502);
  }
}
