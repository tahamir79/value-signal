import type { DerivedFields } from "@/lib/etl";

function formatBillions(value: number | null | undefined) {
  return typeof value === "number" ? `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}B` : "—";
}

function formatPercent(value: number | null | undefined) {
  return typeof value === "number" ? `${value >= 0 ? "+" : ""}${value.toFixed(1)}%` : "—";
}

export function FundamentalsSnapshot({ derived }: { derived: DerivedFields | undefined }) {
  return (
    <section className="fundamentals-section" aria-labelledby="fundamentals-heading">
      <div className="section-head">
        <div>
          <p className="eyebrow">OPERATING SNAPSHOT</p>
          <h2 id="fundamentals-heading">Revenue and margin context.</h2>
        </div>
        <p>These SEC-derived fields are displayed as context. Gross margin is not a standalone official scoring feature.</p>
      </div>
      <div className="scores">
        <article className="score-card"><span>Latest revenue</span><strong>{formatBillions(derived?.latestRevenueBillions)}</strong></article>
        <article className="score-card"><span>Revenue growth</span><strong>{formatPercent(derived?.revenueGrowthPercent)}</strong></article>
        <article className="score-card"><span>Gross margin</span><strong>{formatPercent(derived?.grossMarginPercent)}</strong></article>
        <article className="score-card"><span>Net margin</span><strong>{formatPercent(derived?.netMarginPercent)}</strong></article>
      </div>
    </section>
  );
}

