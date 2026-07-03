import type { SignalDefinition } from "@/types/signal";
export const signalDefinitions: SignalDefinition[] = [
  { id: "potentially-undervalued", label: "Potentially undervalued", tone: "positive", description: "Value evidence is comparatively strong and major risk gates have not been triggered." },
  { id: "quality-watchlist", label: "Quality watchlist", tone: "positive", description: "Business-quality evidence is strong, but the valuation case needs patience or more support." },
  { id: "value-trap-risk", label: "Value trap risk", tone: "caution", description: "A low valuation is accompanied by weakening quality or elevated balance-sheet concerns." },
  { id: "momentum-risk", label: "Momentum risk", tone: "caution", description: "Recent price behavior adds uncertainty to an otherwise researchable company." },
  { id: "neutral", label: "Neutral", tone: "neutral", description: "The current evidence is mixed and does not support a stronger research classification." },
  { id: "insufficient-evidence", label: "Insufficient evidence", tone: "unknown", description: "Required observations are missing or too stale for a responsible classification." },
];
export const signalById = Object.fromEntries(signalDefinitions.map((signal) => [signal.id, signal])) as Record<SignalDefinition["id"], SignalDefinition>;
