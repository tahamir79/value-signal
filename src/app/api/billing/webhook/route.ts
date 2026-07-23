import { NextResponse, type NextRequest } from "next/server";
import { claimStripeEvent, getSubscriptionByCustomer, upsertSubscription } from "@/lib/billing-store";
import { normalizeSubscriptionStatus } from "@/lib/billing-policy";
import { stripeEventFromBody } from "@/lib/stripe-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type StripeObject = Record<string, unknown>;

function stripeString(value: unknown) {
  return typeof value === "string" ? value : null;
}

function stripeBoolean(value: unknown) {
  return value === true;
}

function periodEnd(value: unknown) {
  const seconds = typeof value === "number" ? value : Number(value);
  return Number.isFinite(seconds) && seconds > 0 ? new Date(seconds * 1000).toISOString() : null;
}

function metadataUserId(object: StripeObject) {
  const metadata = object.metadata;
  return metadata && typeof metadata === "object" ? stripeString((metadata as StripeObject).valueSignalUserId) : null;
}

async function userIdFromCustomer(customerId: string | null) {
  if (!customerId) return null;
  return (await getSubscriptionByCustomer(customerId))?.userId ?? null;
}

async function applySubscriptionLike(object: StripeObject, fallbackUserId?: string | null) {
  const customerId = stripeString(object.customer);
  const userId = metadataUserId(object) ?? fallbackUserId ?? await userIdFromCustomer(customerId);
  if (!userId) return;
  const items = object.items && typeof object.items === "object" ? (object.items as { data?: StripeObject[] }).data ?? [] : [];
  const firstPrice = items[0]?.price && typeof items[0].price === "object" ? items[0].price as StripeObject : null;
  await upsertSubscription({
    userId,
    stripeCustomerId: customerId,
    stripeSubscriptionId: stripeString(object.id),
    stripeProductId: stripeString(firstPrice?.product),
    stripePriceId: stripeString(firstPrice?.id),
    status: normalizeSubscriptionStatus(object.status),
    currentPeriodEnd: periodEnd(object.current_period_end),
    cancelAtPeriodEnd: stripeBoolean(object.cancel_at_period_end),
  });
}

async function applyCheckoutSession(object: StripeObject) {
  const userId = metadataUserId(object) ?? stripeString(object.client_reference_id);
  if (!userId) return;
  await upsertSubscription({
    userId,
    stripeCustomerId: stripeString(object.customer),
    stripeSubscriptionId: stripeString(object.subscription),
    stripeProductId: process.env.STRIPE_VALUE_SIGNAL_PRODUCT_ID || null,
    stripePriceId: null,
    status: object.payment_status === "paid" ? "active" : object.payment_status === "unpaid" ? "unpaid" : "incomplete",
    currentPeriodEnd: null,
    cancelAtPeriodEnd: false,
  });
}

async function applyInvoice(object: StripeObject, paid: boolean) {
  const customerId = stripeString(object.customer);
  const userId = await userIdFromCustomer(customerId);
  if (!userId) return;
  await upsertSubscription({
    userId,
    stripeCustomerId: customerId,
    stripeSubscriptionId: stripeString(object.subscription),
    stripeProductId: process.env.STRIPE_VALUE_SIGNAL_PRODUCT_ID || null,
    stripePriceId: null,
    status: paid ? "active" : "past_due",
    currentPeriodEnd: periodEnd(object.lines && typeof object.lines === "object" ? ((object.lines as { data?: StripeObject[] }).data?.[0]?.period as StripeObject | undefined)?.end : null),
    cancelAtPeriodEnd: false,
  });
}

export async function POST(request: NextRequest) {
  const rawBody = await request.text();
  let event: { id: string; type: string; data?: { object?: StripeObject } };
  try {
    event = stripeEventFromBody(rawBody, request.headers.get("stripe-signature"));
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Invalid Stripe webhook." }, { status: 400 });
  }

  const claimed = await claimStripeEvent(event.id, event.type);
  if (!claimed) return NextResponse.json({ received: true, duplicate: true });

  const object = event.data?.object ?? {};
  try {
    if (event.type === "checkout.session.completed" || event.type === "checkout.session.async_payment_succeeded") {
      await applyCheckoutSession(object);
    } else if (event.type === "checkout.session.async_payment_failed") {
      await applyCheckoutSession({ ...object, payment_status: "unpaid" });
    } else if (event.type === "invoice.paid") {
      await applyInvoice(object, true);
    } else if (event.type === "invoice.payment_failed") {
      await applyInvoice(object, false);
    } else if (
      event.type === "customer.subscription.created" ||
      event.type === "customer.subscription.updated" ||
      event.type === "customer.subscription.deleted"
    ) {
      await applySubscriptionLike(object);
    }
  } catch (err) {
    console.error("Stripe webhook processing failed", event.type, err instanceof Error ? err.message : err);
    return NextResponse.json({ error: "Stripe webhook processing failed." }, { status: 500 });
  }

  return NextResponse.json({ received: true });
}
