import type { Metadata } from "next";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { SignalBadge } from "@/components/signals/SignalBadge";
import { signalDefinitions } from "@/data/signals";

export const metadata: Metadata = { title: "Methodology" };

const scoringPrinciples = [
  {
    title: "Value",
    text: "Relative valuation and yield-style evidence. Higher value scores mean the company appears cheaper on the available normalized inputs, not that it is automatically attractive.",
  },
  {
    title: "Quality",
    text: "Profitability, operating durability, and balance-sheet support. Higher quality scores indicate stronger available evidence after missing inputs are removed from the denominator.",
  },
  {
    title: "Momentum",
    text: "Recent price behavior used as context. Momentum is not treated as a forecast; weak or unstable price behavior can reduce conviction through momentum-risk checks.",
  },
  {
    title: "Risk",
    text: "Market risk, balance-sheet risk, missing data, and filing-based caveats. Risk scores run in the unfavorable direction: higher risk means more caution.",
  },
];

const transparencyNotes = [
  "Prices, SEC company facts, balance-sheet fields, features, scores, and filing search indexes are generated as versioned JSON artifacts under public/data.",
  "The ETL pipeline is provider-aware and ticker-isolated: one company failure is logged in the ETL report without stopping the full universe refresh.",
  "SEC-derived fundamentals are normalized for dates, units, fiscal periods, nulls, and comparable feature names before scoring.",
  "Official scores stay on a 0-100 scale. Value, quality, and momentum are favorable when higher; market risk, momentum risk, and balance-sheet risk are worse when higher.",
  "Balance-sheet scoring is now part of the official signal process while the standalone balance-sheet artifact remains visible for inspection.",
  "Missing or stale evidence reduces confidence and can force an insufficient-evidence label instead of allowing the system to overstate precision.",
  "Signals are deterministic rule outputs, not LLM outputs. The RAG layer, when available, may explain or challenge evidence but does not overwrite the official signal.",
  "The weekday data refresh publishes regenerated artifacts through the repository. The public site updates after the workflow commits the artifacts and Vercel redeploys.",
];

const researchBoundaries = [
  "ValueSignal does not produce buy, sell, or hold recommendations.",
  "No score accounts for a specific investor's objectives, constraints, taxes, liquidity needs, or risk tolerance.",
  "SEC facts can be amended, restated, unavailable, or difficult to compare across sectors; the app exposes confidence and warnings rather than hiding those gaps.",
  "A strong signal means the company may deserve deeper research. It does not predict future price direction or guarantee performance.",
];

export default function MethodologyPage() {
  return (
    <div className="page methodology">
      <header className="page-head">
        <p className="eyebrow">METHODOLOGY / LIVE RESEARCH SYSTEM</p>
        <h1>Transparent by construction.</h1>
        <p>ValueSignal is designed to support a research process, not replace judgment. Every classification keeps its inputs, transformations, risk gates, confidence level, and limitations visible.</p>
      </header>
      <Disclaimer />
      <section className="method-block">
        <span>01</span>
        <div>
          <p className="eyebrow">RESEARCH CONTRACT</p>
          <h2>What VS is trying to answer</h2>
          <blockquote>Which public companies may deserve deeper research, what quantitative evidence supports the signal, what risks weaken it, and what public filing evidence explains the business context?</blockquote>
        </div>
      </section>
      <section className="method-block">
        <span>02</span>
        <div>
          <p className="eyebrow">EVIDENCE MODEL</p>
          <h2>Four dimensions, kept separate</h2>
          <div className="dimension-grid">
            {scoringPrinciples.map((item) => (
              <article key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
      <section className="method-block">
        <span>03</span>
        <div>
          <p className="eyebrow">CLASSIFICATION</p>
          <h2>The six-signal taxonomy</h2>
          <div className="method-signals">
            {signalDefinitions.map((signal) => (
              <article key={signal.id}>
                <SignalBadge signal={signal.id} />
                <p>{signal.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
      <section className="method-block">
        <span>04</span>
        <div>
          <p className="eyebrow">SCORING AND DATA TRANSPARENCY</p>
          <h2>How the system stays auditable</h2>
          <div className="method-transparency">
            <article>
              <h3>Pipeline lineage</h3>
              <ul className="limitations">
                {transparencyNotes.slice(0, 4).map((note) => <li key={note}>{note}</li>)}
              </ul>
            </article>
            <article>
              <h3>Signal discipline</h3>
              <ul className="limitations">
                {transparencyNotes.slice(4).map((note) => <li key={note}>{note}</li>)}
              </ul>
            </article>
          </div>
        </div>
      </section>
      <section className="method-block">
        <span>05</span>
        <div>
          <p className="eyebrow">RESEARCH BOUNDARIES</p>
          <h2>What users should and should not infer</h2>
          <ul className="limitations">
            {researchBoundaries.map((boundary) => <li key={boundary}>{boundary}</li>)}
          </ul>
        </div>
      </section>
    </div>
  );
}
