import { signalById } from "@/data/signals";
import type { SignalId } from "@/types/signal";
export function SignalBadge({ signal }: { signal: SignalId }) { const item = signalById[signal]; return <span className={`signal-badge signal-${item.tone}`}>{item.label}</span>; }
