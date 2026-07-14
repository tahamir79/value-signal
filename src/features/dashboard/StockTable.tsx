"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { SignalBadge } from "@/components/signals/SignalBadge";
import type { StockRecord } from "@/types/stock";

type SortKey = "ticker" | "value" | "quality" | "momentum" | "confidence" | "price";

const confidenceRank = { High: 4, Medium: 3, Low: 2, Insufficient: 1 };
const PAGE_SIZE = 50;
const score = (value: number | null) => value === null ? "—" : value.toFixed(1);

export function StockTable({ records, totalUniverseCount = records.length, isAuthenticated = false }: { records: StockRecord[]; totalUniverseCount?: number; isAuthenticated?: boolean }) {
  const [query, setQuery] = useState("");
  const [signal, setSignal] = useState("all");
  const [exchange, setExchange] = useState("all");
  const [confidence, setConfidence] = useState("all");
  const [sort, setSort] = useState<SortKey>("ticker");
  const [descending, setDescending] = useState(false);
  const [page, setPage] = useState(1);

  const signals = useMemo(() => Array.from(new Set(records.map((item) => item.signal))).sort(), [records]);
  const exchanges = useMemo(() => Array.from(new Set(records.map((item) => item.exchange).filter(Boolean))).sort(), [records]);

  const visible = useMemo(() => records.filter((item) => {
    const matchesQuery = `${item.ticker} ${item.companyName} ${item.sector}`.toLowerCase().includes(query.trim().toLowerCase());
    return matchesQuery
      && (signal === "all" || item.signal === signal)
      && (exchange === "all" || item.exchange === exchange)
      && (confidence === "all" || item.confidence === confidence);
  }).sort((a, b) => {
    const values: { [K in SortKey]: [string | number, string | number] } = {
      ticker: [a.ticker, b.ticker],
      value: [a.scores.value ?? -1, b.scores.value ?? -1],
      quality: [a.scores.quality ?? -1, b.scores.quality ?? -1],
      momentum: [a.scores.momentum ?? -1, b.scores.momentum ?? -1],
      confidence: [confidenceRank[a.confidence], confidenceRank[b.confidence]],
      price: [a.price, b.price],
    };
    const [left, right] = values[sort];
    const result = typeof left === "string" ? left.localeCompare(String(right)) : left - Number(right);
    return descending ? -result : result;
  }), [records, query, signal, exchange, confidence, sort, descending]);

  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = visible.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const lockedCount = Math.max(0, totalUniverseCount - records.length);

  function resetPage() {
    setPage(1);
  }

  function changeSort(key: SortKey) {
    if (sort === key) setDescending((value) => !value);
    else {
      setSort(key);
      setDescending(key !== "ticker");
    }
    resetPage();
  }

  const sortButton = (label: string, key: SortKey) => (
    <button type="button" onClick={() => changeSort(key)}>
      {label}
      <span aria-hidden="true">{sort === key ? (descending ? " ↓" : " ↑") : " ↕"}</span>
    </button>
  );

  return <>
    <div className="screen-controls" role="search" aria-label="Filter research universe">
      <label>
        <span>Search</span>
        <input value={query} onChange={(event) => { setQuery(event.target.value); resetPage(); }} placeholder="Ticker, company, or sector" />
      </label>
      <label>
        <span>Signal</span>
        <select value={signal} onChange={(event) => { setSignal(event.target.value); resetPage(); }}>
          <option value="all">All signals</option>
          {signals.map((value) => <option key={value} value={value}>{value.replaceAll("-", " ")}</option>)}
        </select>
      </label>
      <label>
        <span>Exchange</span>
        <select value={exchange} onChange={(event) => { setExchange(event.target.value); resetPage(); }}>
          <option value="all">All exchanges</option>
          {exchanges.map((value) => <option key={value}>{value}</option>)}
        </select>
      </label>
      <label>
        <span>Confidence</span>
        <select value={confidence} onChange={(event) => { setConfidence(event.target.value); resetPage(); }}>
          <option value="all">All confidence</option>
          {["High", "Medium", "Low", "Insufficient"].map((value) => <option key={value}>{value}</option>)}
        </select>
      </label>
      <div className="result-count" role="status" aria-live="polite">
        <strong>{visible.length}</strong>
        <span>{isAuthenticated ? `of ${totalUniverseCount} companies` : `preview of ${totalUniverseCount}`}</span>
      </div>
    </div>
    {visible.length ? <>
      <div className={`table-shell${!isAuthenticated && lockedCount ? " preview-table-shell" : ""}`}>
        <table>
          <caption className="sr-only">Company research signals; use column buttons to sort</caption>
          <thead>
            <tr>
              <th aria-sort={sort === "ticker" ? (descending ? "descending" : "ascending") : "none"}>{sortButton("Company", "ticker")}</th>
              <th>Signal</th>
              <th aria-sort={sort === "value" ? (descending ? "descending" : "ascending") : "none"}>{sortButton("Value", "value")}</th>
              <th aria-sort={sort === "quality" ? (descending ? "descending" : "ascending") : "none"}>{sortButton("Quality", "quality")}</th>
              <th aria-sort={sort === "momentum" ? (descending ? "descending" : "ascending") : "none"}>{sortButton("Momentum", "momentum")}</th>
              <th aria-sort={sort === "confidence" ? (descending ? "descending" : "ascending") : "none"}>{sortButton("Confidence", "confidence")}</th>
              <th>Data status</th>
              <th aria-sort={sort === "price" ? (descending ? "descending" : "ascending") : "none"}>{sortButton("Price", "price")}</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((stock) => (
              <tr key={stock.ticker}>
                <td><Link href={`/stock/${stock.ticker}`}><strong>{stock.ticker}</strong><span>{stock.companyName}</span></Link></td>
                <td><SignalBadge signal={stock.signal} /></td>
                <td>{score(stock.scores.value)}</td>
                <td>{score(stock.scores.quality)}</td>
                <td>{score(stock.scores.momentum)}</td>
                <td>{stock.confidence}</td>
                <td><small>{stock.dataStatus?.scoringAvailable ? "Scored" : "Insufficient"} · {stock.dataStatus?.bm25Indexed ? "Searchable" : "No BM25"} · {stock.dataStatus?.balanceSheetAvailable ? "BS full" : stock.dataStatus?.balanceSheetPartial ? "BS partial" : "No BS"}</small></td>
                <td>${stock.price.toFixed(2)}<small className={stock.dailyChangePercent >= 0 ? "up" : "down"}>{stock.dailyChangePercent >= 0 ? "+" : ""}{stock.dailyChangePercent.toFixed(2)}%</small></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!isAuthenticated && lockedCount ? (
        <div className="universe-lock" role="region" aria-label="Full universe locked behind Google sign-in">
          <div>
            <p className="eyebrow">FULL UNIVERSE LOCKED</p>
            <h3>{lockedCount} more companies are available after sign-in.</h3>
            <p>The public preview shows the original ten-stock ValueSignal universe. Sign in with Google to screen the full scaled universe and open company-level evidence pages beyond the preview set.</p>
          </div>
          <GoogleSignInButton label="Log in using Google" callbackURL="/dashboard" />
        </div>
      ) : null}
      {isAuthenticated ? (
        <div className="pagination-controls" aria-label="Dashboard pagination">
          <button type="button" disabled={safePage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>
          <span>Page {safePage} of {pageCount}</span>
          <button type="button" disabled={safePage === pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>Next</button>
        </div>
      ) : null}
    </> : <div className="table-empty" role="status">
      <h3>No companies match these filters.</h3>
      <p>Clear the search or broaden the signal, exchange, and confidence filters.</p>
      <button type="button" onClick={() => { setQuery(""); setSignal("all"); setExchange("all"); setConfidence("all"); resetPage(); }}>Reset filters</button>
    </div>}
  </>;
}
