import assert from "node:assert/strict";
import test from "node:test";
import { hasProAccess } from "../src/lib/billing-policy";
import { selectAccessibleStocks } from "../src/lib/access-policy";
import type { Entitlement, UserSubscription } from "../src/types/billing";
import type { StockRecord } from "../src/types/stock";

function subscription(status: UserSubscription["status"], currentPeriodEnd: string | null = null): UserSubscription {
  return {
    userId: "user_1",
    stripeCustomerId: "cus_1",
    stripeSubscriptionId: "sub_1",
    stripeProductId: "prod_1",
    stripePriceId: "price_1",
    plan: status === "active" || status === "trialing" ? "pro" : "free",
    status,
    currentPeriodEnd,
    cancelAtPeriodEnd: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function stock(ticker: string, overrides: Partial<StockRecord> = {}): StockRecord {
  return {
    ticker,
    companyName: `${ticker} Corp`,
    sector: "Test",
    exchange: "NYSE",
    price: 10,
    dailyChangePercent: 0,
    marketCapBillions: 1,
    signal: "neutral",
    confidence: "Medium",
    scores: { value: 50, quality: 50, momentum: 50, balanceSheetRisk: 50 },
    summary: "Test stock",
    supportingEvidence: [],
    weakeningEvidence: [],
    asOf: "2026-07-23",
    ...overrides,
  };
}

const publicEntitlement: Entitlement = { accessLevel: "public", isAuthenticated: false, isPro: false, subscription: null };
const freeEntitlement: Entitlement = { accessLevel: "free", isAuthenticated: true, isPro: false, subscription: null };
const proEntitlement: Entitlement = { accessLevel: "pro", isAuthenticated: true, isPro: true, subscription: subscription("active") };

test("subscription entitlement only grants Pro for active/trialing or paid-period cancellation", () => {
  assert.equal(hasProAccess(subscription("active")), true);
  assert.equal(hasProAccess(subscription("trialing")), true);
  assert.equal(hasProAccess(subscription("past_due")), false);
  assert.equal(hasProAccess(subscription("canceled", "2099-01-01T00:00:00.000Z")), true);
  assert.equal(hasProAccess(subscription("canceled", "2020-01-01T00:00:00.000Z")), false);
});

test("access policy separates public, free, and pro dashboard universes", () => {
  const records = [
    stock("AAPL"),
    stock("MSFT"),
    stock("U1", { signal: "potentially-undervalued" }),
    stock("U2", { signal: "potentially-undervalued" }),
    stock("U3", { signal: "potentially-undervalued" }),
    stock("U4", { signal: "potentially-undervalued" }),
    stock("G1", { growthSpurt: { ticker: "G1", generatedAt: "", marketDataAsOf: null, status: "detected", growthSpurtScore: 88, primaryWindowSessions: 63, confirmationWindowSessions: 21, metrics: {} as never, scoreBreakdown: {} as never, warnings: [] } }),
    stock("G2", { growthSpurt: { ticker: "G2", generatedAt: "", marketDataAsOf: null, status: "emerging", growthSpurtScore: 61, primaryWindowSessions: 63, confirmationWindowSessions: 21, metrics: {} as never, scoreBreakdown: {} as never, warnings: [] } }),
    stock("G3", { growthSpurt: { ticker: "G3", generatedAt: "", marketDataAsOf: null, status: "detected", growthSpurtScore: 77, primaryWindowSessions: 63, confirmationWindowSessions: 21, metrics: {} as never, scoreBreakdown: {} as never, warnings: [] } }),
    stock("G4", { growthSpurt: { ticker: "G4", generatedAt: "", marketDataAsOf: null, status: "detected", growthSpurtScore: 80, primaryWindowSessions: 63, confirmationWindowSessions: 21, metrics: {} as never, scoreBreakdown: {} as never, warnings: [] } }),
  ];
  assert.deepEqual(selectAccessibleStocks(records, publicEntitlement).records.map((item) => item.ticker), ["AAPL", "MSFT"]);
  assert.deepEqual(selectAccessibleStocks(records, freeEntitlement).records.map((item) => item.ticker), ["AAPL", "MSFT", "U1", "U2", "U3", "G1", "G2", "G3"]);
  assert.equal(selectAccessibleStocks(records, proEntitlement).records.length, records.length);
});
