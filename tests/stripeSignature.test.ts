import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";
import { verifyStripeSignature } from "../src/lib/stripe-signature";

function signature(rawBody: string, secret: string, timestamp = Math.floor(Date.now() / 1000)) {
  const digest = createHmac("sha256", secret).update(`${timestamp}.${rawBody}`).digest("hex");
  return `t=${timestamp},v1=${digest}`;
}

test("Stripe webhook signature verification accepts valid signed raw body", () => {
  const rawBody = JSON.stringify({ id: "evt_test", type: "invoice.paid" });
  assert.doesNotThrow(() => verifyStripeSignature(rawBody, signature(rawBody, "whsec_test"), "whsec_test"));
});

test("Stripe webhook signature verification rejects tampered body", () => {
  const rawBody = JSON.stringify({ id: "evt_test", type: "invoice.paid" });
  assert.throws(() => verifyStripeSignature(`${rawBody} `, signature(rawBody, "whsec_test"), "whsec_test"));
});
