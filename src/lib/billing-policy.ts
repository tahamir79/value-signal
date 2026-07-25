import type { SubscriptionStatus, UserSubscription } from "@/types/billing";

const PRO_STATUSES = new Set<SubscriptionStatus>(["active", "trialing"]);

export function normalizeSubscriptionStatus(value: unknown): SubscriptionStatus {
  const status = String(value ?? "none");
  if (
    status === "incomplete" ||
    status === "trialing" ||
    status === "active" ||
    status === "past_due" ||
    status === "paused" ||
    status === "canceled" ||
    status === "unpaid" ||
    status === "incomplete_expired"
  ) {
    return status;
  }
  return "none";
}

export function subscriptionMatchesStripeMode(subscription: UserSubscription | null, currentLivemode: boolean | null) {
  if (!subscription) return false;
  if (currentLivemode === null) return true;
  return subscription.stripeLivemode === currentLivemode;
}

export function hasProAccess(subscription: UserSubscription | null, now = new Date(), currentLivemode: boolean | null = null) {
  if (!subscription) return false;
  if (!subscriptionMatchesStripeMode(subscription, currentLivemode)) return false;
  if (PRO_STATUSES.has(subscription.status)) return true;
  if (subscription.status === "canceled" && subscription.currentPeriodEnd) {
    return new Date(subscription.currentPeriodEnd).getTime() > now.getTime();
  }
  return false;
}

export function planForStatus(status: SubscriptionStatus): "free" | "pro" {
  return status === "active" || status === "trialing" ? "pro" : "free";
}
