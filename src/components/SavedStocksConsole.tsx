"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { HoldingOutcomeGrid } from "@/components/HoldingOutcomeCard";
import { formatDisplayDate, formatShareQuantity } from "@/lib/display-format";
import { calculatePositionProjection } from "@/lib/position-projections";
import type { ForecastArtifact, ForecastSummary } from "@/types/forecast";
import type { PortfolioPosition, WatchlistItem } from "@/types/user-records";

type LoadState = "idle" | "loading" | "ready" | "error";
type QuantityType = "shares" | "dollar_amount";
type PositionStatus = "owned" | "planned";

type PortfolioDraft = {
  positionStatus: PositionStatus;
  quantityType: QuantityType;
  quantity: string;
  return30: string;
  return90: string;
};

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || "Request failed.");
  return payload as T;
}

function decimalFromPercent(value: string) {
  if (!value.trim()) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric / 100 : null;
}

function percentFromDecimal(value: number | null) {
  return value === null ? "" : (value * 100).toString();
}

function money(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "Unavailable";
}

function percent(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%` : "Unavailable";
}
function modelStatus(name: string | undefined, validationStatus: string | undefined) {
  if (!name) return "Unavailable";
  if (name === "zero-return baseline" || name === "historical-mean baseline" || name === "market-return baseline") return "Baseline benchmark";
  return validationStatus ?? "Experimental";
}

function draftFromPosition(position: PortfolioPosition): PortfolioDraft {
  return {
    positionStatus: position.positionStatus,
    quantityType: position.quantityType,
    quantity: position.quantityType === "shares" ? String(position.shares ?? "") : String(position.dollarAmount ?? ""),
    return30: percentFromDecimal(position.userReturnEstimate30Day),
    return90: percentFromDecimal(position.userReturnEstimate90Day),
  };
}

async function loadForecastMap() {
  try {
    const response = await fetch("/data/forecasts/summary.json", { cache: "no-store" });
    if (!response.ok) return {};
    const payload = (await response.json()) as ForecastSummary;
    return Object.fromEntries((payload.forecasts ?? []).map((forecast) => [forecast.ticker, forecast])) as Record<string, ForecastArtifact>;
  } catch {
    return {};
  }
}

export function SavedStocksConsole() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioPosition[]>([]);
  const [forecasts, setForecasts] = useState<Record<string, ForecastArtifact>>({});
  const [drafts, setDrafts] = useState<Record<string, PortfolioDraft>>({});
  const [status, setStatus] = useState<LoadState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [watchTicker, setWatchTicker] = useState("");
  const [portfolioTicker, setPortfolioTicker] = useState("");
  const [quantityType, setQuantityType] = useState<QuantityType>("dollar_amount");
  const [quantity, setQuantity] = useState("");
  const [return30, setReturn30] = useState("");
  const [return90, setReturn90] = useState("");
  const [positionStatus, setPositionStatus] = useState<PositionStatus>("planned");

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
      const forecastMap = await loadForecastMap();
      setWatchlist(watchlistPayload.records);
      setPortfolio(portfolioPayload.records);
      setForecasts(forecastMap);
      setDrafts(Object.fromEntries(portfolioPayload.records.map((position) => [position.id, draftFromPosition(position)])));
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
          userReturnEstimate30Day: decimalFromPercent(return30),
          userReturnEstimate90Day: decimalFromPercent(return90),
        }),
      });
      setPortfolioTicker("");
      setQuantity("");
      setReturn30("");
      setReturn90("");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save Portfolio position.");
    }
  }

  async function updatePortfolio(position: PortfolioPosition) {
    const draft = drafts[position.id];
    if (!draft) return;
    const numericQuantity = Number(draft.quantity);
    setMessage(null);
    try {
      await jsonFetch(`/api/portfolio/${encodeURIComponent(position.id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          ticker: position.ticker,
          positionStatus: draft.positionStatus,
          quantityType: draft.quantityType,
          shares: draft.quantityType === "shares" && Number.isFinite(numericQuantity) ? numericQuantity : null,
          dollarAmount: draft.quantityType === "dollar_amount" && Number.isFinite(numericQuantity) ? numericQuantity : null,
          averageCostPerShare: position.averageCostPerShare,
          userReturnEstimate30Day: decimalFromPercent(draft.return30),
          userReturnEstimate90Day: decimalFromPercent(draft.return90),
          notes: position.notes,
        }),
      });
      setMessage(`${position.ticker} scenario was updated.`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update Portfolio position.");
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
        <div className="inline-form portfolio-form scenario-form">
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
            <select value={quantityType} onChange={(event) => setQuantityType(event.target.value === "shares" ? "shares" : "dollar_amount")}>
              <option value="dollar_amount">Dollar amount</option>
              <option value="shares">Shares</option>
            </select>
          </label>
          <label>
            <span>{quantityType === "shares" ? "Shares" : "Allocated amount"}</span>
            <input value={quantity} onChange={(event) => setQuantity(event.target.value)} inputMode="decimal" placeholder={quantityType === "shares" ? "10" : "5000"} />
          </label>
          <details className="personal-scenario-panel">
            <summary>Try your own scenario</summary>
            <div className="personal-scenario-grid">
              <label>
                <span>Personal 30-Day Scenario %</span>
                <input value={return30} onChange={(event) => setReturn30(event.target.value)} inputMode="decimal" placeholder="3" />
              </label>
              <label>
                <span>Personal 90-Day Scenario %</span>
                <input value={return90} onChange={(event) => setReturn90(event.target.value)} inputMode="decimal" placeholder="8" />
              </label>
            </div>
            <small>Optional percentages entered by you. They do not change ValueSignal estimates or market-target scenarios.</small>
          </details>
          <button type="button" onClick={() => void addPortfolio()}>Save Position</button>
        </div>
        <p className="form-disclaimer">Portfolio records are research notes only. ValueSignal projections and market-target scenarios are uncertain research estimates, not guarantees or investment advice.</p>
        <div className="saved-list portfolio-list">
          {portfolio.map((position) => {
            const draft = drafts[position.id] ?? draftFromPosition(position);
            const draftQuantity = Number(draft.quantity);
            const allocatedValue = draft.quantityType === "dollar_amount" ? draftQuantity : null;
            const baseValue = allocatedValue !== null && Number.isFinite(allocatedValue) && allocatedValue > 0 ? allocatedValue : null;
            const forecast = forecasts[position.ticker];
            const projection = calculatePositionProjection({
              quantityType: draft.quantityType,
              shares: draft.quantityType === "shares" && Number.isFinite(draftQuantity) ? draftQuantity : null,
              dollarAmount: draft.quantityType === "dollar_amount" ? baseValue : null,
              averageCostPerShare: position.averageCostPerShare,
            }, forecast);

            return (
              <article key={position.id} className="portfolio-position-card">
                <div>
                  <strong>{position.ticker}</strong>
                  <span>{position.companyName}</span>
                  <small>
                    {draft.positionStatus === "owned" ? "Owned" : "Planned"} · {draft.quantityType === "shares" ? `${draft.quantity || "—"} shares` : `${money(baseValue)} allocation`}
                  </small>
                  <dl className="position-current-summary">
                    <div>
                      <dt>Current price</dt>
                      <dd>{money(projection.currentPrice)}</dd>
                    </div>
                    <div>
                      <dt>Current position value</dt>
                      <dd>{money(projection.currentPositionValue)}</dd>
                    </div>
                    {draft.quantityType === "dollar_amount" ? (
                      <div>
                        <dt>Allocation</dt>
                        <dd>{money(baseValue)}</dd>
                      </div>
                    ) : null}
                    <div>
                      <dt>{projection.shareLabel}</dt>
                      <dd>{formatShareQuantity(projection.sharesHeld)}</dd>
                    </div>
                    <div>
                      <dt>Market data as of</dt>
                      <dd>{formatDisplayDate(projection.marketDataAsOf)}</dd>
                    </div>
                  </dl>
                </div>
                <div className="position-editor" aria-label={`${position.ticker} scenario editor`}>
                  <label>
                    <span>Status</span>
                    <select value={draft.positionStatus} onChange={(event) => setDrafts((current) => ({ ...current, [position.id]: { ...draft, positionStatus: event.target.value === "owned" ? "owned" : "planned" } }))}>
                      <option value="planned">Planned</option>
                      <option value="owned">Owned</option>
                    </select>
                  </label>
                  <label>
                    <span>Type</span>
                    <select value={draft.quantityType} onChange={(event) => setDrafts((current) => ({ ...current, [position.id]: { ...draft, quantityType: event.target.value === "shares" ? "shares" : "dollar_amount" } }))}>
                      <option value="dollar_amount">Dollar amount</option>
                      <option value="shares">Shares</option>
                    </select>
                  </label>
                  <label>
                    <span>{draft.quantityType === "shares" ? "Shares" : "Allocation"}</span>
                    <input value={draft.quantity} onChange={(event) => setDrafts((current) => ({ ...current, [position.id]: { ...draft, quantity: event.target.value } }))} inputMode="decimal" />
                  </label>
                  <details className="personal-scenario-panel">
                    <summary>Try your own scenario</summary>
                    <div className="personal-scenario-grid">
                      <label>
                        <span>Personal 30-Day Scenario %</span>
                        <input value={draft.return30} onChange={(event) => setDrafts((current) => ({ ...current, [position.id]: { ...draft, return30: event.target.value } }))} inputMode="decimal" />
                      </label>
                      <label>
                        <span>Personal 90-Day Scenario %</span>
                        <input value={draft.return90} onChange={(event) => setDrafts((current) => ({ ...current, [position.id]: { ...draft, return90: event.target.value } }))} inputMode="decimal" />
                      </label>
                    </div>
                    <small>These personal percentages stay separate from generated ValueSignal and market-target outcomes.</small>
                  </details>
                </div>
                <HoldingOutcomeGrid outcomes={projection.outcomes} />
                <p className="form-disclaimer">ValueSignal projections and market-target scenarios are uncertain research estimates, not guarantees or investment advice. Market-target scenarios may be time-scaled from a longer-horizon analyst consensus target and are not direct analyst forecasts for 30 or 90 days. Actual outcomes may differ materially.</p>
                <details className="forecast-details">
                  <summary>Forecast methodology</summary>
                  <dl className="forecast-meta-grid">
                    <div><dt>ValueSignal 30-day model</dt><dd>{forecast?.model30Day.name ?? "Unavailable"}</dd><small>{modelStatus(forecast?.model30Day.name, forecast?.validationStatus)}</small></div>
                    <div><dt>ValueSignal 90-day model</dt><dd>{forecast?.model90Day.name ?? "Unavailable"}</dd><small>{modelStatus(forecast?.model90Day.name, forecast?.validationStatus)}</small></div>
                    <div><dt>Displayed projection</dt><dd>{projection.horizon30Day.sourceLabel}</dd><small>{projection.horizon30Day.sourceDetail}{projection.horizon30Day.sampleCount ? ` · ${projection.horizon30Day.sampleCount} samples` : ""}</small></div>
                    <div><dt>Market target status</dt><dd>{forecast?.analystTarget.status ?? "Unsupported"}</dd><small>{forecast?.analystTarget.warnings?.[0] ?? "Analyst target data is not currently available."}</small></div>
                    <div><dt>Personal 30-day scenario</dt><dd>{percent(decimalFromPercent(draft.return30))}</dd><small>User-entered; not used by ValueSignal estimates.</small></div>
                    <div><dt>Personal 90-day scenario</dt><dd>{percent(decimalFromPercent(draft.return90))}</dd><small>User-entered; not used by market-target scenarios.</small></div>
                  </dl>
                </details>
                <div className="saved-actions">
                  <Link href={`/stock/${position.ticker}`}>Open</Link>
                  <button type="button" onClick={() => void updatePortfolio(position)}>Update</button>
                  <button type="button" onClick={() => void removePortfolio(position.id)}>Remove</button>
                </div>
              </article>
            );
          })}
          {!portfolio.length && status !== "loading" ? <p className="empty-note">No Portfolio positions yet.</p> : null}
        </div>
      </section>
      {status === "loading" ? <p className="form-disclaimer" role="status">Loading saved stocks…</p> : null}
      {message ? <p className="load-warning" role="alert">{message}</p> : null}
    </div>
  );
}
