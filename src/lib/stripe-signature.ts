import { createHmac, timingSafeEqual } from "node:crypto";

export function verifyStripeSignature(rawBody: string, signatureHeader: string | null, webhookSecret = process.env.STRIPE_WEBHOOK_SECRET) {
  if (!webhookSecret) throw new Error("STRIPE_WEBHOOK_SECRET is required.");
  if (!signatureHeader) throw new Error("Stripe signature header is missing.");
  const parts = Object.fromEntries(signatureHeader.split(",").map((part) => {
    const [key, value] = part.split("=", 2);
    return [key, value];
  }));
  const timestamp = parts.t;
  const signatures = signatureHeader.split(",").filter((part) => part.startsWith("v1=")).map((part) => part.slice(3));
  if (!timestamp || !signatures.length) throw new Error("Stripe signature header is malformed.");
  const ageSeconds = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (!Number.isFinite(ageSeconds) || ageSeconds > 300) throw new Error("Stripe signature timestamp is outside the tolerance window.");
  const expected = createHmac("sha256", webhookSecret).update(`${timestamp}.${rawBody}`).digest("hex");
  const expectedBuffer = Buffer.from(expected, "hex");
  const valid = signatures.some((signature) => {
    const actualBuffer = Buffer.from(signature, "hex");
    return actualBuffer.length === expectedBuffer.length && timingSafeEqual(actualBuffer, expectedBuffer);
  });
  if (!valid) throw new Error("Stripe webhook signature verification failed.");
}
