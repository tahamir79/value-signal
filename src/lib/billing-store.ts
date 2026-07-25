import "server-only";

import { Pool, type QueryResultRow } from "pg";
import { hasProAccess, normalizeSubscriptionStatus, planForStatus, subscriptionMatchesStripeMode } from "@/lib/billing-policy";
import type { Entitlement, SubscriptionStatus, UserSubscription } from "@/types/billing";

declare global {
  // eslint-disable-next-line no-var
  var valueSignalBillingPool: Pool | undefined;
  // eslint-disable-next-line no-var
  var valueSignalBillingTablesReady: Promise<void> | undefined;
}

function pool() {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is required for ValueSignal subscription records.");
  }

  globalThis.valueSignalBillingPool ??= new Pool({
    connectionString: process.env.DATABASE_URL,
    connectionTimeoutMillis: 10_000,
  });

  return globalThis.valueSignalBillingPool;
}

export function currentStripeLivemode() {
  const key = process.env.STRIPE_SECRET_KEY || "";
  if (key.startsWith("sk_live_")) return true;
  if (key.startsWith("sk_test_")) return false;
  return null;
}

function iso(value: unknown) {
  if (value === null || value === undefined) return null;
  return value instanceof Date ? value.toISOString() : String(value);
}

function subscriptionFromRow(row: QueryResultRow): UserSubscription {
  const status = normalizeSubscriptionStatus(row.status);
  return {
    userId: String(row.userId),
    stripeCustomerId: row.stripeCustomerId ? String(row.stripeCustomerId) : null,
    stripeSubscriptionId: row.stripeSubscriptionId ? String(row.stripeSubscriptionId) : null,
    stripeProductId: row.stripeProductId ? String(row.stripeProductId) : null,
    stripePriceId: row.stripePriceId ? String(row.stripePriceId) : null,
    stripeLivemode: typeof row.stripeLivemode === "boolean" ? row.stripeLivemode : null,
    plan: row.plan === "pro" ? "pro" : planForStatus(status),
    status,
    currentPeriodEnd: iso(row.currentPeriodEnd),
    cancelAtPeriodEnd: Boolean(row.cancelAtPeriodEnd),
    createdAt: iso(row.createdAt) ?? new Date().toISOString(),
    updatedAt: iso(row.updatedAt) ?? new Date().toISOString(),
  };
}

export async function ensureBillingTables() {
  globalThis.valueSignalBillingTablesReady ??= pool().query(`
    create table if not exists "user_subscription" (
      "userId" text not null primary key references "user" ("id") on delete cascade,
      "stripeCustomerId" text unique,
      "stripeSubscriptionId" text unique,
      "stripeProductId" text,
      "stripePriceId" text,
      "stripeLivemode" boolean,
      "plan" text default 'free' not null check ("plan" in ('free', 'pro')),
      "status" text default 'none' not null check ("status" in ('none', 'incomplete', 'trialing', 'active', 'past_due', 'paused', 'canceled', 'unpaid', 'incomplete_expired')),
      "currentPeriodEnd" timestamptz,
      "cancelAtPeriodEnd" boolean default false not null,
      "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
      "updatedAt" timestamptz default CURRENT_TIMESTAMP not null
    );
    alter table "user_subscription" add column if not exists "stripeLivemode" boolean;
    create index if not exists "user_subscription_status_idx" on "user_subscription" ("status");
    create table if not exists "processed_stripe_event" (
      "stripeEventId" text not null primary key,
      "eventType" text not null,
      "processedAt" timestamptz default CURRENT_TIMESTAMP not null
    );
  `).then(() => undefined);
  return globalThis.valueSignalBillingTablesReady;
}

export async function getUserSubscription(userId: string) {
  await ensureBillingTables();
  const result = await pool().query(`select * from "user_subscription" where "userId" = $1`, [userId]);
  return result.rows[0] ? subscriptionFromRow(result.rows[0]) : null;
}

export async function getSubscriptionByCustomer(stripeCustomerId: string) {
  await ensureBillingTables();
  const livemode = currentStripeLivemode();
  const result = livemode === null
    ? await pool().query(`select * from "user_subscription" where "stripeCustomerId" = $1`, [stripeCustomerId])
    : await pool().query(`select * from "user_subscription" where "stripeCustomerId" = $1 and "stripeLivemode" = $2`, [stripeCustomerId, livemode]);
  return result.rows[0] ? subscriptionFromRow(result.rows[0]) : null;
}

export async function upsertCustomerForUser(userId: string, stripeCustomerId: string) {
  await ensureBillingTables();
  const result = await pool().query(
    `insert into "user_subscription" ("userId", "stripeCustomerId", "stripeLivemode", "updatedAt")
     values ($1, $2, $3, CURRENT_TIMESTAMP)
     on conflict ("userId") do update set
       "stripeCustomerId" = excluded."stripeCustomerId",
       "stripeLivemode" = excluded."stripeLivemode",
       "updatedAt" = CURRENT_TIMESTAMP
     returning *`,
    [userId, stripeCustomerId, currentStripeLivemode()],
  );
  return subscriptionFromRow(result.rows[0]);
}

export async function upsertSubscription(input: {
  userId: string;
  stripeCustomerId: string | null;
  stripeSubscriptionId: string | null;
  stripeProductId: string | null;
  stripePriceId: string | null;
  status: SubscriptionStatus;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
}) {
  await ensureBillingTables();
  const result = await pool().query(
    `insert into "user_subscription"
      ("userId", "stripeCustomerId", "stripeSubscriptionId", "stripeProductId", "stripePriceId", "stripeLivemode", "plan", "status", "currentPeriodEnd", "cancelAtPeriodEnd", "updatedAt")
     values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP)
     on conflict ("userId") do update set
       "stripeCustomerId" = coalesce(excluded."stripeCustomerId", "user_subscription"."stripeCustomerId"),
       "stripeSubscriptionId" = coalesce(excluded."stripeSubscriptionId", "user_subscription"."stripeSubscriptionId"),
       "stripeProductId" = coalesce(excluded."stripeProductId", "user_subscription"."stripeProductId"),
       "stripePriceId" = coalesce(excluded."stripePriceId", "user_subscription"."stripePriceId"),
       "stripeLivemode" = excluded."stripeLivemode",
       "plan" = excluded."plan",
       "status" = excluded."status",
       "currentPeriodEnd" = excluded."currentPeriodEnd",
       "cancelAtPeriodEnd" = excluded."cancelAtPeriodEnd",
       "updatedAt" = CURRENT_TIMESTAMP
     returning *`,
    [
      input.userId,
      input.stripeCustomerId,
      input.stripeSubscriptionId,
      input.stripeProductId,
      input.stripePriceId,
      currentStripeLivemode(),
      planForStatus(input.status),
      input.status,
      input.currentPeriodEnd,
      input.cancelAtPeriodEnd,
    ],
  );
  return subscriptionFromRow(result.rows[0]);
}

export async function claimStripeEvent(stripeEventId: string, eventType: string) {
  await ensureBillingTables();
  const result = await pool().query(
    `insert into "processed_stripe_event" ("stripeEventId", "eventType")
     values ($1, $2)
     on conflict ("stripeEventId") do nothing`,
    [stripeEventId, eventType],
  );
  return (result.rowCount ?? 0) > 0;
}

export async function entitlementForUser(userId: string | null | undefined): Promise<Entitlement> {
  if (!userId) return { accessLevel: "public", isAuthenticated: false, isPro: false, subscription: null };
  const subscription = await getUserSubscription(userId);
  const currentMode = currentStripeLivemode();
  const modeMatches = subscriptionMatchesStripeMode(subscription, currentMode);
  const effectiveSubscription = modeMatches ? subscription : null;
  const isPro = hasProAccess(effectiveSubscription, new Date(), currentMode);
  return {
    accessLevel: isPro ? "pro" : "free",
    isAuthenticated: true,
    isPro,
    subscription: effectiveSubscription,
  };
}
