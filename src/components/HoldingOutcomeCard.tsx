import React from "react";
import type { HoldingOutcome } from "@/types/forecast";

function money(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `$${value.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}` : "Unavailable";
}

function signedMoney(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  return `${value >= 0 ? "+" : "-"}$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
}

function percent(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%` : "Unavailable";
}

function shares(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function range(outcome: HoldingOutcome) {
  if (typeof outcome.lowerReturn === "number" && Number.isFinite(outcome.lowerReturn) && typeof outcome.upperReturn === "number" && Number.isFinite(outcome.upperReturn)) {
    return `${percent(outcome.lowerReturn)} to ${percent(outcome.upperReturn)}`;
  }
  if (typeof outcome.lowerEstimatedPositionValue === "number" && typeof outcome.upperEstimatedPositionValue === "number") {
    return `${money(outcome.lowerEstimatedPositionValue)} to ${money(outcome.upperEstimatedPositionValue)}`;
  }
  return null;
}

export function HoldingOutcomeCard({ outcome }: { outcome: HoldingOutcome }) {
  const unavailable = outcome.status === "unavailable";
  const cardRange = range(outcome);
  const isMarketTarget = outcome.source === "market_target";
  const prefix = isMarketTarget ? "Market-implied" : "Estimated";
  return (
    <article className={`holding-outcome-card ${isMarketTarget ? "market-target" : "valuesignal"} ${unavailable ? "unavailable" : ""}`}>
      <header>
        <span>{outcome.label}</span>
        <strong>{unavailable ? "Unavailable" : signedMoney(outcome.estimatedGainLoss)}</strong>
        {!unavailable ? <small>{prefix} total gain/loss</small> : null}
      </header>
      {unavailable ? (
        <p className="outcome-unavailable">
          {isMarketTarget ? `Market-target scenario unavailable. Analyst target data or target horizon is not available.${outcome.unavailableReason ? ` Reason: ${outcome.unavailableReason}` : ""}` : outcome.unavailableReason ?? "Scenario unavailable"}
        </p>
      ) : (
        <dl>
          <div>
            <dt>{prefix} gain/loss per share</dt>
            <dd>{signedMoney(outcome.estimatedGainLossPerShare)}</dd>
          </div>
          <div>
            <dt>Shares held</dt>
            <dd>{shares(outcome.sharesHeld)}</dd>
          </div>
          <div>
            <dt>{prefix} total gain/loss</dt>
            <dd>{signedMoney(outcome.estimatedGainLoss)}</dd>
          </div>
          <div>
            <dt>{prefix} sell price</dt>
            <dd>{money(outcome.estimatedSellPrice)}</dd>
          </div>
          <div>
            <dt>{prefix} position value</dt>
            <dd>{money(outcome.estimatedPositionValue)}</dd>
          </div>
          <div>
            <dt>{prefix} return percentage</dt>
            <dd>{percent(outcome.estimatedReturn)}</dd>
          </div>
        </dl>
      )}
      <footer>
        {cardRange && !unavailable ? <small>Scenario range: {cardRange}</small> : null}
        <small>As of: {outcome.asOf ?? "Unavailable"}</small>
        <small>Source: {outcome.methodology ?? outcome.sourceProvider ?? "Unavailable"}</small>
        {outcome.source === "market_target" ? (
          <small>
            Provider: {outcome.sourceProvider ?? "Unavailable"} · Target horizon: {outcome.sourceHorizonDays ? `${outcome.sourceHorizonDays} days` : "Unavailable"}
          </small>
        ) : null}
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

