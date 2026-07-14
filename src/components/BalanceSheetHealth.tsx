import type { BalanceSheetScoringOutput } from "@/lib/etl";

const labels: Record<string, string> = {
  currentRatio: "Current ratio",
  quickRatio: "Quick ratio",
  cashRatio: "Cash ratio",
  workingCapital: "Working capital",
  debtToEquity: "Debt / equity",
  debtToAssets: "Debt / assets",
  equityRatio: "Equity ratio",
  cashToDebt: "Cash / debt",
  netDebt: "Net debt",
  goodwillIntangiblesToAssets: "Goodwill + intangibles / assets",
  shortTermDebtShare: "Short-term debt share",
  bookValue: "Book value",
};

const statusLabel = (value: string) => value.replaceAll("_", " ");
const fmt = (value: number | null) => typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—";

export function BalanceSheetHealth({ scoring }: { scoring: BalanceSheetScoringOutput | undefined }) {
  if (!scoring) {
    return (
      <section className="balance-sheet-section">
        <div className="section-head">
          <div>
            <p className="eyebrow">BALANCE SHEET HEALTH</p>
            <h2>No balance-sheet scoring available.</h2>
          </div>
        </div>
      </section>
    );
  }

  const gates = (scoring.triggeredRiskGates ?? []).filter((gate) => gate.triggered);

  return (
    <section className="balance-sheet-section">
      <div className="section-head">
        <div>
          <p className="eyebrow">BALANCE SHEET HEALTH / OFFICIAL CONTEXT</p>
          <h2>Liquidity, leverage, solvency, and asset quality.</h2>
        </div>
        <p>Higher quality is better; higher risk penalty is worse. Official scoring now blends these audited balance-sheet checks into quality, balance-sheet risk, confidence, and signal review gates.</p>
      </div>
      <div className="scores">
        <article className="score-card"><span>Liquidity</span><strong>{fmt(scoring.liquidityScore)}</strong></article>
        <article className="score-card"><span>Leverage safety</span><strong>{fmt(scoring.leverageScore)}</strong></article>
        <article className="score-card"><span>Solvency</span><strong>{fmt(scoring.solvencyScore)}</strong></article>
        <article className="score-card"><span>Asset quality</span><strong>{fmt(scoring.assetQualityScore)}</strong></article>
        <article className="score-card inverse"><span>Risk penalty</span><strong>{fmt(scoring.balanceSheetRiskPenalty)}</strong></article>
      </div>
      {gates.length ? (
        <article className="risk-panel">
          <p className="eyebrow">TRIGGERED GATES</p>
          <ul>{gates.map((gate) => <li key={gate.name}>{gate.name}: {gate.explanation}</li>)}</ul>
        </article>
      ) : <p className="muted-copy">No balance-sheet risk gates triggered.</p>}
      <div className="component-card">
        <table>
          <thead>
            <tr><th>Metric</th><th>Company value</th><th>Healthy range</th><th>Status</th><th>Interpretation</th></tr>
          </thead>
          <tbody>
            {(scoring.targetComparisons ?? []).map((item) => (
              <tr key={item.metric}>
                <td>{labels[item.metric] ?? item.metric}</td>
                <td>{fmt(item.value)}</td>
                <td>{item.healthyRange}</td>
                <td>{statusLabel(item.status)}</td>
                <td>{item.interpretation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {scoring.warnings?.length ? (
        <details className="chat-evidence">
          <summary>Balance-sheet warnings</summary>
          <ul>{scoring.warnings.slice(0, 12).map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </details>
      ) : null}
    </section>
  );
}
