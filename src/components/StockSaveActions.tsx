"use client";

import { useState } from "react";

async function postJson(url: string, body: unknown) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || "Request failed.");
  return payload;
}

export function StockSaveActions({ ticker }: { ticker: string }) {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function saveWatchlist() {
    setBusy("watchlist");
    setMessage(null);
    try {
      await postJson("/api/watchlist", { ticker });
      setMessage(`${ticker} is on your Watchlist.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save Watchlist stock.");
    } finally {
      setBusy(null);
    }
  }

  async function savePlannedPosition() {
    setBusy("portfolio");
    setMessage(null);
    try {
      await postJson("/api/portfolio", { ticker, positionStatus: "planned", quantityType: "dollar_amount", dollarAmount: 1 });
      setMessage(`${ticker} was added as a planned Portfolio note. Edit the amount on Saved Stocks.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save Portfolio position.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="stock-save-actions" aria-label="Saved stock actions">
      <button type="button" onClick={() => void saveWatchlist()} disabled={busy !== null}>
        {busy === "watchlist" ? "Saving…" : "Add to Watchlist"}
      </button>
      <button type="button" onClick={() => void savePlannedPosition()} disabled={busy !== null}>
        {busy === "portfolio" ? "Saving…" : "Add planned Portfolio note"}
      </button>
      {message ? <small role="status">{message}</small> : null}
    </div>
  );
}
