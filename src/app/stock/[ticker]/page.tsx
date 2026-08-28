import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AnalystBrief } from "@/components/AnalystBrief";
import { AnalystSummary } from "@/components/AnalystSummary";
import { BalanceSheetHealth } from "@/components/BalanceSheetHealth";
import { FilingEvidencePanel } from "@/components/FilingEvidencePanel";
import { FundamentalsSnapshot } from "@/components/FundamentalsSnapshot";
import { GrowthSpurtBadge } from "@/components/GrowthSpurtBadge";
import { PriceChart } from "@/components/PriceChart";
import { RagTeaser } from "@/components/RagTeaser";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { SignalBadge } from "@/components/signals/SignalBadge";
import { StockSaveActions } from "@/components/StockSaveActions";
import { UniverseLockPanel } from "@/components/UniverseLockPanel";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { ScoreCard } from "@/features/stock-detail/ScoreCard";
import { generateAnalystBrief } from "@/lib/briefGenerator";
import { canAccessStock } from "@/lib/access-policy";
import { entitlementForUser } from "@/lib/billing-store";
import { getBacktestData } from "@/lib/etl";
import { isPublicPreviewTicker } from "@/lib/public-universe";
import { getResearchStockDetail, getResearchStocks } from "@/lib/research";
import { searchFilings } from "@/lib/search";
import { getCurrentSession } from "@/lib/server-auth";

export function generateStaticParams() {
  return [];
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ ticker: string }> }): Promise<Metadata> {
  const detail = await getResearchStockDetail((await params).ticker);
  return { title: detail ? `${detail.stock.ticker} research` : "Company not found" };
}

export default async function StockPage({ params }: { params: Promise<{ ticker: string }> }) {
  const ticker = (await params).ticker.toUpperCase();
  const session = await getCurrentSession();
  const entitlement = await entitlementForUser(session?.user?.id);

  if (!session?.user && !isPublicPreviewTicker(ticker)) {
    return (
      <div className="page stock-page">
        <Link className="back-link" href="/dashboard">← Back to dashboard</Link>
        <Disclaimer />
        <UniverseLockPanel ticker={ticker} />
      </div>
    );
  }

  if (session?.user && !entitlement.isPro) {
    const allRecords = await getResearchStocks();
    if (!canAccessStock(ticker, allRecords, entitlement)) {
      return (
        <div className="page stock-page">
          <Link className="back-link" href="/dashboard">← Back to dashboard</Link>
          <Disclaimer />
          <UniverseLockPanel ticker={ticker} mode="pro" />
        </div>
      );
    }
  }

  const [detail, filingEvidence, backtest] = await Promise.all([
    getResearchStockDetail(ticker),
    searchFilings(ticker, "risk factors", 3),
    getBacktestData(),
  ]);
  if (!detail) notFound();
  const { stock, dashboardRecord, signalRecord } = detail;
  const brief = generateAnalystBrief(stock.ticker, signalRecord, filingEvidence, backtest);
  const balanceSheetScoring = dashboardRecord?.balanceSheetScoringShadow ?? signalRecord?.balanceSheetScoringShadow;

  return (
    <div className="page stock-page">
      <Link className="back-link" href="/dashboard">← Back to dashboard</Link>
      <header className="stock-head">
        <div>
          <p className="eyebrow">{stock.exchange} / {stock.sector}</p>
          <h1>{stock.ticker}</h1>
          <p>{stock.companyName}</p>
        </div>
        <div className="quote">
          <strong>${stock.price.toFixed(2)}</strong>
          <span className={stock.dailyChangePercent >= 0 ? "up" : "down"}>
            {stock.dailyChangePercent >= 0 ? "+" : ""}{stock.dailyChangePercent.toFixed(2)}%
          </span>
          <small>{dashboardRecord ? "Latest successful ETL observation" : "Fallback observation"}</small>
        </div>
      </header>
      {session?.user ? <StockSaveActions ticker={stock.ticker} /> : null}
      <Disclaimer />
      <section className="signal-summary">
        <div>
          <p className="eyebrow">CURRENT RESEARCH SIGNAL</p>
          <SignalBadge signal={stock.signal} />
          <h2>{stock.summary}</h2>
        </div>
        <dl>
          <div><dt>Confidence</dt><dd>{stock.confidence}</dd></div>
          <div><dt>Market cap</dt><dd>${stock.marketCapBillions.toLocaleString()}B</dd></div>
          <div><dt>Record date</dt><dd>{stock.asOf}</dd></div>
        </dl>
      </section>
      <AnalystSummary stock={stock} signal={signalRecord} />
      <FundamentalsSnapshot derived={dashboardRecord?.derived} />
      <GrowthSpurtBadge artifact={dashboardRecord?.growthSpurt ?? stock.growthSpurt} variant="detail" />
      <PriceChart prices={dashboardRecord?.priceHistory ?? []} />
      <section className="score-section">
        <div className="section-head">
          <div>
            <p className="eyebrow">SCORE OVERVIEW / V1</p>
            <h2>Inspect, don’t infer.</h2>
          </div>
          <p>Higher risk is unfavorable; other higher scores indicate stronger evidence.</p>
        </div>
        <div className="scores">
          <ScoreCard label="Value" value={stock.scores.value} />
          <ScoreCard label="Quality" value={stock.scores.quality} />
          <ScoreCard label="Momentum" value={stock.scores.momentum} />
          <ScoreCard label="Market risk" value={stock.scores.marketRisk ?? null} inverse />
          <ScoreCard label="Balance-sheet risk" value={stock.scores.balanceSheetRisk} inverse />
        </div>
      </section>
      <ScoreBreakdown signal={signalRecord} />
      <BalanceSheetHealth scoring={balanceSheetScoring} />
      <section className="evidence-grid">
        <article>
          <p className="eyebrow">SUPPORTING EVIDENCE</p>
          {stock.supportingEvidence.length ? <ul>{stock.supportingEvidence.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No supporting reason codes were produced.</p>}
        </article>
        <article className="risk-panel">
          <p className="eyebrow">WHAT WEAKENS THE SIGNAL</p>
          {stock.weakeningEvidence.length ? <ul>{stock.weakeningEvidence.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No weakening reason codes were produced.</p>}
        </article>
      </section>
      <AnalystBrief brief={brief} />
      <FilingEvidencePanel ticker={stock.ticker} initialResults={filingEvidence} />
      <RagTeaser ticker={stock.ticker} companyName={stock.companyName} />
      <section className="next-step">
        <p className="eyebrow">RESEARCH NEXT</p>
        <h2>Validate the source observations, read recent filings, and compare this company with sector peers before forming a view.</h2>
        <Link href="/methodology">Understand how VS classifies evidence →</Link>
      </section>
    </div>
  );
}
