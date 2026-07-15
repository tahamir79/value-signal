"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { PortfolioPosition, WatchlistItem } from "@/types/user-records";

type LoadState = "idle" | "loading" | "ready" | "error";

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || "Request failed.");
  return payload as T;
}

export function SavedStocksConsole() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioPosition[]>([]);
  const [status, setStatus] = useState<LoadState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [watchTicker, setWatchTicker] = useState("");
  const [portfolioTicker, setPortfolioTicker] = useState("");
  const [quantityType, setQuantityType] = useState<"shares" | "dollar_amount">("shares");
  const [quantity, setQuantity] = useState("");
  const [positionStatus, setPositionStatus] = useState<"owned" | "planned">("planned");

  const portfolioValueInputName = quantityType === "shares" ? "shares" : "dollarAmount";
  const portfolioTotal = useMemo(() => portfolio.length, [portfolio.length]);

  async function refresh() {
    setStatus("loading");
    setMessage(null);
    try {
      const [watchlistPayload, portfolioPayload] = await Promise.all([
        jsonFetch<{ records: WatchlistItem[] }>("/api/watchlist"),
        jsonFetch<{ records: PortfolioPosition[] }>("/api/portfolio"),
      ]);
      setWatchlist(watchlistPayload.records);
      setPortfolio(portfolioPayload.records);
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Could not load saved stocks.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function addWatchlist() {
    setMessage(null);
    try {
      await jsonFetch("/api/watchlist", { method: "POST", body: JSON.stringify({ ticker: watchTicker }) });
      setWatchTicker("");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not add Watchlist stock.");
    }
  }

  async function removeWatchlist(ticker: string) {
    setMessage(null);
    try {
      await jsonFetch(`/api/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not remove Watchlist stock.");
    }
  }

  async function addPortfolio() {
    setMessage(null);
    const numericQuantity = Number(quantity);
    try {
      await jsonFetch("/api/portfolio", {
        method: "POST",
        body: JSON.stringify({
          ticker: portfolioTicker,
          positionStatus,
          quantityType,
          [portfolioValueInputName]: Number.isFinite(numericQuantity) ? numericQuantity : null,
        }),
      });
      setPortfolioTicker("");
      setQuantity("");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save Portfolio position.");
    }
  }

  async function removePortfolio(positionId: string) {
    setMessage(null);
    try {
      await jsonFetch(`/api/portfolio/${encodeURIComponent(positionId)}`, { method: "DELETE" });
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not remove Portfolio position.");
    }
  }

  return (
    <div className="saved-console">
      <section className="saved-panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">MY WATCHLIST</p>
            <h2>Stocks to monitor or research</h2>
          </div>
          <span className="pill">{watchlist.length} saved</span>
        </div>
        <div className="inline-form">
          <label>
            <span>Ticker</span>
            <input value={watchTicker} onChange={(event) => setWatchTicker(event.target.value.toUpperCase())} placeholder="GOOGL" />
          </label>
          <button type="button" onClick={() => void addWatchlist()}>Add to Watchlist</button>
        </div>
        <div className="saved-list">
          {watchlist.map((item) => (
            <article key={item.id}>
              <div>
                <strong>{item.ticker}</strong>
                <span>{item.companyName}</span>
                <small>Filing alerts {item.filingAlerts ? "on" : "off"} · signal alerts {item.signalChangeAlerts ? "on" : "off"}</small>
              </div>
              <div className="saved-actions">
                <Link href={`/stock/${item.ticker}`}>Open</Link>
                <button type="button" onClick={() => void removeWatchlist(item.ticker)}>Remove</button>
              </div>
            </article>
          ))}
          {!watchlist.length && status !== "loading" ? <p className="empty-note">No Watchlist stocks yet.</p> : null}
        </div>
      </section>
      <section className="saved-panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">MY PORTFOLIO</p>
            <h2>Owned or planned research positions</h2>
          </div>
          <span className="pill">{portfolioTotal} positions</span>
        </div>
        <div className="inline-form portfolio-form">
          <label>
            <span>Ticker</span>
            <input value={portfolioTicker} onChange={(event) => setPortfolioTicker(event.target.value.toUpperCase())} placeholder="MSFT" />
          </label>
          <label>
            <span>Status</span>
            <select value={positionStatus} onChange={(event) => setPositionStatus(event.target.value === "owned" ? "owned" : "planned")}>
              <option value="planned">Planned</option>
              <option value="owned">Owned</option>
            </select>
          </label>
          <label>
            <span>Quantity type</span>
            <select value={quantityType} onChange={(event) => setQuantityType(event.target.value === "dollar_amount" ? "dollar_amount" : "shares")}>
              <option value="shares">Shares</option>
              <option value="dollar_amount">Dollar amount</option>
            </select>
          </label>
          <label>
            <span>{quantityType === "shares" ? "Shares" : "Dollar amount"}</span>
            <input value={quantity} onChange={(event) => setQuantity(event.target.value)} inputMode="decimal" placeholder={quantityType === "shares" ? "10" : "5000"} />
          </label>
          <button type="button" onClick={() => void addPortfolio()}>Save Position</button>
        </div>
        <p className="form-disclaimer">Portfolio records are research notes only. ValueSignal does not execute trades or recommend share quantities.</p>
        <div className="saved-list">
          {portfolio.map((position) => (
            <article key={position.id}>
              <div>
                <strong>{position.ticker}</strong>
                <span>{position.companyName}</span>
                <small>
                  {position.positionStatus === "owned" ? "Owned" : "Planned"} · {position.quantityType === "shares" ? `${position.shares} shares` : `$${position.dollarAmount?.toLocaleString()} allocation`}
                </small>
              </div>
              <div className="saved-actions">
                <Link href={`/stock/${position.ticker}`}>Open</Link>
                <button type="button" onClick={() => void removePortfolio(position.id)}>Remove</button>
              </div>
            </article>
          ))}
          {!portfolio.length && status !== "loading" ? <p className="empty-note">No Portfolio positions yet.</p> : null}
        </div>
      </section>
      {status === "loading" ? <p className="form-disclaimer" role="status">Loading saved stocks…</p> : null}
      {message ? <p className="load-warning" role="alert">{message}</p> : null}
    </div>
  );
}
