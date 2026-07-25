import "server-only";

import { upsertCustomerForUser } from "@/lib/billing-store";
import { verifyStripeSignature } from "@/lib/stripe-signature";

export const STRIPE_MANAGED_PAYMENTS_API_VERSION = process.env.STRIPE_API_VERSION || "2025-03-31.basil";

type StripeUser = { id: string; email?: string | null; name?: string | null };
type StripeObject = Record<string, unknown>;

class StripeRequestError extends Error {
  constructor(message: string, readonly status: number, readonly code: string | null, readonly param: string | null) {
    super(message);
    this.name = "StripeRequestError";
  }
}

export function missingStripeCheckoutEnv(interval: "month" | "year" = "month") {
  const required = ["STRIPE_SECRET_KEY", "STRIPE_VALUE_SIGNAL_MONTHLY_PRICE_ID", "NEXT_PUBLIC_APP_URL"] as const;
  const missing = required.filter((name) => !process.env[name]);
  if (interval === "year" && !process.env.STRIPE_VALUE_SIGNAL_ANNUAL_PRICE_ID) {
    return [...missing, "STRIPE_VALUE_SIGNAL_ANNUAL_PRICE_ID"];
  }
  return missing;
}

function secretKey() {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error("STRIPE_SECRET_KEY is required.");
  if (!key.startsWith("sk_test_") && !key.startsWith("sk_live_")) {
    throw new Error("STRIPE_SECRET_KEY must be a Stripe secret key that starts with sk_test_ or sk_live_.");
  }
  return key;
}

function appUrl() {
  return (process.env.NEXT_PUBLIC_APP_URL || process.env.BETTER_AUTH_URL || "http://localhost:3000").replace(/\/+$/, "");
}

async function stripeRequest<T extends StripeObject>(path: string, init: RequestInit = {}) {
  const response = await fetch(`https://api.stripe.com${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${secretKey()}`,
      "Stripe-Version": STRIPE_MANAGED_PAYMENTS_API_VERSION,
      ...(init.body ? { "Content-Type": "application/x-www-form-urlencoded" } : {}),
      ...(init.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload?.error?.message === "string" ? payload.error.message : `Stripe request failed with ${response.status}.`;
    const code = typeof payload?.error?.code === "string" ? payload.error.code : null;
    const param = typeof payload?.error?.param === "string" ? payload.error.param : null;
    throw new StripeRequestError(message, response.status, code, param);
  }
  return payload as T;
}

function formBody(entries: Record<string, string | number | boolean | null | undefined>) {
  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(entries)) {
    if (value !== undefined && value !== null && value !== "") body.set(key, String(value));
  }
  return body;
}

function stripeString(value: unknown) {
  return typeof value === "string" ? value : null;
}

function isMissingStripeCustomer(error: unknown) {
  return error instanceof StripeRequestError
    && error.status === 404
    && (error.code === "resource_missing" || error.message.toLowerCase().includes("no such customer"));
}

async function verifiedStripeCustomerId(customerId: string) {
  try {
    const customer = await stripeRequest<StripeObject>(`/v1/customers/${encodeURIComponent(customerId)}`);
    if (customer.deleted === true) return null;
    return stripeString(customer.id);
  } catch (error) {
    if (isMissingStripeCustomer(error)) return null;
    throw error;
  }
}

export async function findStripeCustomerForUser(userId: string) {
  const query = `metadata['valueSignalUserId']:'${userId.replaceAll("'", "\\'")}'`;
  try {
    const result = await stripeRequest<{ data?: StripeObject[] }>(`/v1/customers/search?${new URLSearchParams({ query, limit: "1" })}`);
    return stripeString(result.data?.[0]?.id);
  } catch {
    return null;
  }
}

export async function getOrCreateStripeCustomer(user: StripeUser, existingCustomerId?: string | null) {
  if (existingCustomerId) {
    const verified = await verifiedStripeCustomerId(existingCustomerId);
    if (verified) return verified;
  }
  const found = await findStripeCustomerForUser(user.id);
  if (found) {
    await upsertCustomerForUser(user.id, found);
    return found;
  }
  const customer = await stripeRequest<StripeObject>("/v1/customers", {
    method: "POST",
    body: formBody({
      email: user.email || undefined,
      name: user.name || undefined,
      "metadata[valueSignalUserId]": user.id,
    }),
  });
  const customerId = stripeString(customer.id);
  if (!customerId) throw new Error("Stripe did not return a customer ID.");
  await upsertCustomerForUser(user.id, customerId);
  return customerId;
}

export async function createValueSignalCheckoutSession(input: {
  user: StripeUser;
  stripeCustomerId: string;
  interval: "month" | "year";
}) {
  const priceId =
    input.interval === "year"
      ? process.env.STRIPE_VALUE_SIGNAL_ANNUAL_PRICE_ID
      : process.env.STRIPE_VALUE_SIGNAL_MONTHLY_PRICE_ID;
  if (!priceId) throw new Error(`${input.interval === "year" ? "Annual" : "Monthly"} Stripe price is not configured.`);

  return stripeRequest<StripeObject>("/v1/checkout/sessions", {
    method: "POST",
    body: formBody({
      "line_items[0][price]": priceId,
      "line_items[0][quantity]": 1,
      mode: "subscription",
      "managed_payments[enabled]": true,
      customer: input.stripeCustomerId,
      client_reference_id: input.user.id,
      success_url: `${appUrl()}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${appUrl()}/billing/cancel`,
      "metadata[valueSignalUserId]": input.user.id,
      "metadata[valueSignalPlan]": "pro",
      "metadata[valueSignalInterval]": input.interval,
      "subscription_data[metadata][valueSignalUserId]": input.user.id,
      "subscription_data[metadata][valueSignalPlan]": "pro",
      "subscription_data[metadata][valueSignalInterval]": input.interval,
    }),
  });
}

export function stripeEventFromBody(rawBody: string, signatureHeader: string | null) {
  verifyStripeSignature(rawBody, signatureHeader);
  return JSON.parse(rawBody) as { id: string; type: string; data?: { object?: StripeObject } };
}
