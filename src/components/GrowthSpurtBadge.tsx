import React from "react";
import type { GrowthSpurtArtifact, GrowthSpurtStatus } from "@/types/stock";

const statusCopy: Record<GrowthSpurtStatus, { label: string; compact: string; tone: string }> = {
  detected: { label: "✅ Growth spurt detected", compact: "✅ Growth spurt", tone: "detected" },
  emerging: { label: "↗ Emerging upward trend", compact: "↗ Emerging", tone: "emerging" },
  not_detected: { label: "No growth spurt detected", compact: "No tag", tone: "neutral" },
  unavailable: { label: "Trend history unavailable", compact: "Unavailable", tone: "unavailable" },
};

function formatScore(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${Math.round(value)}/100`;
}

function formatPercent(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}

function formatPercentile(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}th`;
}

function consistencyLabel(value: number | null | undefined) {
  if (value === null || value === undefined) return "Unavailable";
  if (value >= 0.7) return "Strong";
  if (value >= 0.45) return "Moderate";
  return "Weak";
}

function asOf(value: string | null | undefined) {
  if (!value) return "Not available";
  return value;
}

export function GrowthSpurtBadge({
  artifact,
  variant = "compact",
}: {
  artifact?: GrowthSpurtArtifact | null;
  variant?: "compact" | "detail";
}) {
  const status = artifact?.status ?? "unavailable";
  const copy = statusCopy[status];
  const title = artifact
    ? `${copy.label}. Score ${formatScore(artifact.growthSpurtScore)}. 63-day return ${formatPercent(artifact.metrics.return63d)}. SPY excess ${formatPercent(artifact.metrics.excessReturnVsSpy63d)}.`
    : "Growth Spurt detector unavailable.";

  if (variant === "compact") {
    return (
      <span className={`growth-spurt-badge growth-spurt-${copy.tone}`} title={title} aria-label={title}>
        {copy.compact}
      </span>
    );
  }

  return (
    <section className={`growth-spurt-card growth-spurt-${copy.tone}`} aria-label="Recent trend growth spurt detector">
      <div className="section-head compact-head">
        <div>
          <p className="eyebrow">RECENT TREND / DISPLAY-ONLY</p>
          <h2>Recent price behavior</h2>
        </div>
        <GrowthSpurtBadge artifact={artifact} />
      </div>
      <p className="growth-spurt-definition">
        {status === "detected"
          ? "Steady upward price behavior detected over the recent three-month period."
          : status === "emerging"
            ? "The recent price path is constructive, but it does not meet every full detection threshold."
            : status === "not_detected"
              ? "The recent price path does not meet the Growth Spurt shape, consistency, relative-strength, and drawdown thresholds."
              : "There is not enough usable recent price and benchmark history to calculate the detector responsibly."}
      </p>
      <dl className="growth-spurt-metrics">
        <div><dt>Score</dt><dd>{formatScore(artifact?.growthSpurtScore)}</dd></div>
        <div><dt>63-day price change</dt><dd>{formatPercent(artifact?.metrics.return63d)}</dd></div>
        <div><dt>SPY-relative change</dt><dd>{formatPercent(artifact?.metrics.excessReturnVsSpy63d)}</dd></div>
        <div><dt>Trend consistency</dt><dd>{consistencyLabel(artifact?.metrics.trendFitR2_63d)}</dd></div>
        <div><dt>Maximum drawdown</dt><dd>{formatPercent(artifact?.metrics.maxDrawdown63d)}</dd></div>
        <div><dt>Universe percentile</dt><dd>{formatPercentile(artifact?.benchmarkPercentile)}</dd></div>
        <div><dt>Positive-week ratio</dt><dd>{formatPercent(artifact?.metrics.positiveWeekRatio63d, 0)}</dd></div>
        <div><dt>As of</dt><dd>{asOf(artifact?.marketDataAsOf)}</dd></div>
      </dl>
      {artifact?.warnings?.length ? (
        <div className="growth-spurt-warnings">
          <strong>Warnings</strong>
          <ul>{artifact.warnings.map((warning) => <li key={warning}>{warning.replaceAll("_", " ").toLowerCase()}</li>)}</ul>
        </div>
      ) : null}
      <p className="growth-spurt-disclosure">
        This tag describes recent historical price behavior. It does not predict that the price will continue rising.
      </p>
    </section>
  );
}
