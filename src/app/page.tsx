import Link from "next/link";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { SignalBadge } from "@/components/signals/SignalBadge";
import { signalDefinitions } from "@/data/signals";
import { getResearchStock } from "@/lib/research";
import { getStock } from "@/data/stocks";

export default async function HomePage() {
  const example=(await getResearchStock("MSFT"))??getStock("MSFT")!;
  return <>
    <section className="hero">
      <div className="hero-copy">
        <p className="eyebrow">PUBLIC-COMPANY RESEARCH / EXPLAINED</p>
        <h1>Find the signal.<br/><em>Keep the evidence.</em></h1>
        <p className="lede">ValueSignal helps you identify companies that may deserve deeper research, understand the quantitative case, and see which risks weaken it.</p>
        <div className="actions"><Link className="button" href="/dashboard">Explore the research dashboard</Link><Link className="text-link" href="/methodology">Read the methodology →</Link></div>
      </div>
      <aside className="research-card" aria-label="Example research signal">
        <div className="card-label"><span>RESEARCH SNAPSHOT</span><span>VS / 001</span></div>
        <div className="ticker-lockup"><div><strong>{example.ticker}</strong><span>{example.companyName}</span></div><SignalBadge signal={example.signal} /></div>
        <dl className="metric-grid"><div><dt>Value</dt><dd>{example.scores.value??"—"}</dd></div><div><dt>Quality</dt><dd>{example.scores.quality??"—"}</dd></div><div><dt>Momentum</dt><dd>{example.scores.momentum??"—"}</dd></div><div><dt>Confidence</dt><dd>{example.confidence}</dd></div></dl>
        <p className="card-note">Live, versioned scoring output. Classification is research support—not financial advice.</p>
      </aside>
    </section>
    <section className="research-question"><p className="eyebrow">THE RESEARCH QUESTION</p><h2>Which companies may deserve deeper research—and what evidence supports or weakens that view?</h2><p>VS separates observations, derived scores, risks, and conclusions so the path from source data to research signal stays inspectable.</p></section>
    <section className="section"><div className="section-head"><div><p className="eyebrow">SIGNAL TAXONOMY</p><h2>Six cautious outcomes.</h2></div><p>Signals organize evidence. They are not forecasts, ratings, or instructions.</p></div><div className="signal-grid">{signalDefinitions.map((item) => <article key={item.id}><SignalBadge signal={item.id}/><h3>{item.label}</h3><p>{item.description}</p></article>)}</div></section>
    <section className="process"><div><span>01</span><h3>Screen</h3><p>Compare a consistent universe of public companies.</p></div><div><span>02</span><h3>Inspect</h3><p>Open the feature, risk, and confidence breakdown.</p></div><div><span>03</span><h3>Research</h3><p>Follow the evidence before forming a conclusion.</p></div></section>
    <div className="section disclaimer-wrap"><Disclaimer /></div>
  </>;
}
