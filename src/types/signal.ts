export const signalIds = ["potentially-undervalued", "quality-watchlist", "value-trap-risk", "momentum-risk", "neutral", "insufficient-evidence"] as const;
export type SignalId = (typeof signalIds)[number];
export type SignalDefinition = { id: SignalId; label: string; description: string; tone: "positive" | "caution" | "neutral" | "unknown" };
