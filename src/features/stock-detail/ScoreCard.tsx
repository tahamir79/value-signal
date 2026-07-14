export function ScoreCard({ label, value, inverse = false }: { label: string; value: number | null; inverse?: boolean }) {
  const width = value ?? 0;
  const displayValue = typeof value === "number" ? value.toFixed(1) : "—";

  return (
    <div className="score-card">
      <div><span>{label}</span><strong>{displayValue}</strong></div>
      <div className="score-track" aria-label={`${label}: ${displayValue}`}>
        <i className={inverse ? "inverse" : ""} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}
