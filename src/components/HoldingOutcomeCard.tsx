import React from "react";
import { formatDisplayDate } from "@/lib/display-format";
import type { HoldingOutcome } from "@/types/forecast";

function money(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? `$${value.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`
    : "Unavailable";
}

function signedMoney(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  if (value === 0) return "$0.00";
  return `${value > 0 ? "+" : "-"}$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
}

function percent(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%` : "Unavailable";
}

function primaryCaption(outcome: HoldingOutcome) {
  if (typeof outcome.estimatedGainLoss !== "number" || !Number.isFinite(outcome.estimatedGainLoss)) return null;
  if (outcome.estimatedGainLoss === 0) return "No estimated change";
  const kind = outcome.estimatedGainLoss > 0 ? "gain" : "loss";
  return outcome.source === "market_target" ? `Market-implied ${kind}` : `Estimated ${kind}`;
}

function perShareLabel(outcome: HoldingOutcome) {
  return typeof outcome.estimatedGainLossPerShare === "number" && Number.isFinite(outcome.estimatedGainLossPerShare) && outcome.estimatedGainLossPerShare < 0
    ? "Loss per share"
    : "Gain per share";
}

function sourceLabel(outcome: HoldingOutcome) {
  if (outcome.methodology === "ValueSignal historical scenario") return "Historical scenario";
  if (outcome.methodology === "ValueSignal forecast model") return "Forecast model";
  return outcome.methodology ?? outcome.sourceProvider ?? null;
}

export function HoldingOutcomeCard({ outcome }: { outcome: HoldingOutcome }) {
  const unavailable = outcome.status === "unavailable";
  const isMarketTarget = outcome.source === "market_target";
  const caption = primaryCaption(outcome);
  const formattedDate = outcome.asOf ? formatDisplayDate(outcome.asOf) : null;
  const conciseReason = isMarketTarget ? "Analyst target data is not currently available." : outcome.unavailableReason ?? "Scenario unavailable";

  return (
    <article className={`holding-outcome-card ${isMarketTarget ? "market-target" : "valuesignal"} ${unavailable ? "unavailable" : ""}`}>
      <header>
        <span>{outcome.label}</span>
        <strong>{unavailable ? "Unavailable" : signedMoney(outcome.estimatedGainLoss)}</strong>
        {!unavailable && caption ? <small>{caption}</small> : null}
      </header>
      {unavailable ? (
        <div className="outcome-unavailable">
          <p>{conciseReason}</p>
          {outcome.unavailableDetail ? <small>{outcome.unavailableDetail}</small> : null}
          {isMarketTarget ? (
            <details>
              <summary>Why unavailable?</summary>
              <small>ValueSignal does not currently have a configured external analyst-target provider.</small>
            </details>
          ) : null}
        </div>
      ) : (
        <dl>
          <div>
            <dt>Return</dt>
            <dd>{percent(outcome.estimatedReturn)}</dd>
          </div>
          <div>
            <dt>Sell price</dt>
            <dd>{money(outcome.estimatedSellPrice)}</dd>
          </div>
          <div>
            <dt>Position value</dt>
            <dd>{money(outcome.estimatedPositionValue)}</dd>
          </div>
          <div>
            <dt>{perShareLabel(outcome)}</dt>
            <dd>{signedMoney(outcome.estimatedGainLossPerShare)}</dd>
          </div>
        </dl>
      )}
      <footer>
        {formattedDate ? <small>As of {formattedDate}</small> : null}
        {!unavailable && sourceLabel(outcome) ? <small>{sourceLabel(outcome)}</small> : null}
      </footer>
    </article>
  );
}

export function HoldingOutcomeGrid({ outcomes }: { outcomes: HoldingOutcome[] }) {
  return (
    <section className="holding-outcome-grid" aria-label="Saved position outcome estimates">
      {outcomes.map((outcome) => (
        <HoldingOutcomeCard key={`${outcome.source}-${outcome.horizonDays}`} outcome={outcome} />
      ))}
    </section>
  );
}
