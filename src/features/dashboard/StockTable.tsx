import Link from "next/link";
import { SignalBadge } from "@/components/signals/SignalBadge";
import type { StockRecord } from "@/types/stock";

const score = (value: number | null) => value === null ? "—" : value;

export function StockTable({ records }: { records: StockRecord[] }) {
  return <div className="table-shell"><table><caption className="sr-only">Placeholder company research signals</caption><thead><tr><th>Company</th><th>Signal</th><th>Value</th><th>Quality</th><th>Momentum</th><th>Confidence</th><th>Price</th></tr></thead><tbody>{records.map((stock) => <tr key={stock.ticker}><td><Link href={`/stock/${stock.ticker}`}><strong>{stock.ticker}</strong><span>{stock.companyName}</span></Link></td><td><SignalBadge signal={stock.signal}/></td><td>{score(stock.scores.value)}</td><td>{score(stock.scores.quality)}</td><td>{score(stock.scores.momentum)}</td><td>{stock.confidence}</td><td>${stock.price.toFixed(2)}<small className={stock.dailyChangePercent >= 0 ? "up" : "down"}>{stock.dailyChangePercent >= 0 ? "+" : ""}{stock.dailyChangePercent.toFixed(2)}%</small></td></tr>)}</tbody></table></div>;
}
