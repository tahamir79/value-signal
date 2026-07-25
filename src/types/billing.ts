export type SubscriptionPlan = "free" | "pro";

export type SubscriptionStatus =
  | "none"
  | "incomplete"
  | "trialing"
  | "active"
  | "past_due"
  | "paused"
  | "canceled"
  | "unpaid"
  | "incomplete_expired";

export type UserSubscription = {
  userId: string;
  stripeCustomerId: string | null;
  stripeSubscriptionId: string | null;
  stripeProductId: string | null;
  stripePriceId: string | null;
  stripeLivemode?: boolean | null;
  plan: SubscriptionPlan;
  status: SubscriptionStatus;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
  createdAt: string;
  updatedAt: string;
};

export type AccessLevel = "public" | "free" | "pro";

export type Entitlement = {
  accessLevel: AccessLevel;
  isAuthenticated: boolean;
  isPro: boolean;
  subscription: UserSubscription | null;
};
