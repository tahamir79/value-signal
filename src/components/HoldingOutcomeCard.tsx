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

function scenarioRange(outcome: HoldingOutcome) {
  if (typeof outcome.lowerReturn !== "number" || !Number.isFinite(outcome.lowerReturn)) return "Unavailable";
  if (typeof outcome.upperReturn !== "number" || !Number.isFinite(outcome.upperReturn)) return "Unavailable";
  return `${percent(outcome.lowerReturn)} to ${percent(outcome.upperReturn)}`;
}

function primaryCaption(outcome: HoldingOutcome) {
  if (typeof outcome.estimatedGainLoss !== "number" || !Number.isFinite(outcome.estimatedGainLoss)) return null;
  if (outcome.estimatedGainLoss === 0) return "No estimated change";
  const kind = outcome.estimatedGainLoss > 0 ? "gain" : "loss";
  return `Estimated total ${kind}`;
}

function perShareLabel(outcome: HoldingOutcome) {
  if (typeof outcome.estimatedGainLossPerShare !== "number" || !Number.isFinite(outcome.estimatedGainLossPerShare)) return "Gain/loss per share";
  if (outcome.estimatedGainLossPerShare > 0) return "Gain per share";
  if (outcome.estimatedGainLossPerShare < 0) return "Loss per share";
  return "Change per share";
}

function sourceLabel(outcome: HoldingOutcome) {
  if (outcome.methodology === "ValueSignal historical scenario") return "Historical scenario";
  if (outcome.methodology === "ValueSignal forecast model") return "Forecast model";
  return outcome.methodology ?? outcome.sourceProvider ?? null;
}

export function HoldingOutcomeCard({ outcome }: { outcome: HoldingOutcome }) {
  const unavailable = outcome.status === "unavailable";
  const caption = primaryCaption(outcome);
  const formattedDate = outcome.asOf ? formatDisplayDate(outcome.asOf) : null;
  const projectionSource = sourceLabel(outcome);
  const conciseReason = outcome.unavailableReason ?? "Scenario unavailable";

  return (
    <article className={`holding-outcome-card ${outcome.source === "market_target" ? "market-target" : "valuesignal"} ${unavailable ? "unavailable" : ""}`}>
      <header>
        <span>{outcome.label}</span>
        <strong>{unavailable ? "Unavailable" : signedMoney(outcome.estimatedGainLoss)}</strong>
        {!unavailable && caption ? <small>{caption}</small> : null}
      </header>
      {unavailable ? (
        <div className="outcome-unavailable">
          <p>{conciseReason}</p>
          {outcome.unavailableDetail ? <small>{outcome.unavailableDetail}</small> : null}
        </div>
      ) : (
        <dl>
          <div>
            <dt>{perShareLabel(outcome)}</dt>
            <dd>{signedMoney(outcome.estimatedGainLossPerShare)}</dd>
          </div>
          <div>
            <dt>Estimated sell price</dt>
            <dd>{money(outcome.estimatedSellPrice)}</dd>
          </div>
          <div>
            <dt>Estimated position value</dt>
            <dd>{money(outcome.estimatedPositionValue)}</dd>
          </div>
          <div>
            <dt>Estimated return</dt>
            <dd>{percent(outcome.estimatedReturn)}</dd>
          </div>
          <div>
            <dt>Scenario range</dt>
            <dd>{scenarioRange(outcome)}</dd>
          </div>
          <div>
            <dt>Projection source</dt>
            <dd>{projectionSource ?? "Unavailable"}</dd>
          </div>
        </dl>
      )}
      <footer>
        {formattedDate ? <small>As of {formattedDate}</small> : null}
      </footer>
    </article>
  );
}

export function HoldingOutcomeGrid({ outcomes }: { outcomes: HoldingOutcome[] }) {
  const valueSignalOutcomes = outcomes.filter((outcome) => outcome.source === "valuesignal");

  return (
    <section className="holding-outcome-grid" aria-label="Saved position outcome estimates">
      {valueSignalOutcomes.map((outcome) => (
        <HoldingOutcomeCard key={`${outcome.source}-${outcome.horizonDays}`} outcome={outcome} />
      ))}
    </section>
  );
}
