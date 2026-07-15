import "server-only";

import { randomUUID } from "node:crypto";
import { Pool, type QueryResultRow } from "pg";
import { getResearchStock } from "@/lib/research";
import type { PortfolioPosition, PortfolioPositionInput, WatchlistAlertPatch, WatchlistItem } from "@/types/user-records";

declare global {
  // eslint-disable-next-line no-var
  var valueSignalUserDataPool: Pool | undefined;
  // eslint-disable-next-line no-var
  var valueSignalUserDataTablesReady: Promise<void> | undefined;
}

function pool() {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is required for saved Watchlist and Portfolio records.");
  }

  globalThis.valueSignalUserDataPool ??= new Pool({
    connectionString: process.env.DATABASE_URL,
    connectionTimeoutMillis: 10_000,
  });

  return globalThis.valueSignalUserDataPool;
}

function bool(value: unknown) {
  return Boolean(value);
}

function iso(value: unknown) {
  return value instanceof Date ? value.toISOString() : String(value);
}

function watchlistFromRow(row: QueryResultRow): WatchlistItem {
  return {
    id: String(row.id),
    userId: String(row.userId),
    ticker: String(row.ticker),
    companyName: String(row.companyName),
    createdAt: iso(row.createdAt),
    alertEnabled: bool(row.alertEnabled),
    companyEventAlerts: bool(row.companyEventAlerts),
    industryEventAlerts: bool(row.industryEventAlerts),
    filingAlerts: bool(row.filingAlerts),
    signalChangeAlerts: bool(row.signalChangeAlerts),
    forecastChangeAlerts: bool(row.forecastChangeAlerts),
  };
}

function portfolioFromRow(row: QueryResultRow): PortfolioPosition {
  return {
    id: String(row.id),
    userId: String(row.userId),
    ticker: String(row.ticker),
    companyName: String(row.companyName),
    positionStatus: row.positionStatus === "owned" ? "owned" : "planned",
    quantityType: row.quantityType === "shares" ? "shares" : "dollar_amount",
    shares: row.shares === null || row.shares === undefined ? null : Number(row.shares),
    dollarAmount: row.dollarAmount === null || row.dollarAmount === undefined ? null : Number(row.dollarAmount),
    averageCostPerShare: row.averageCostPerShare === null || row.averageCostPerShare === undefined ? null : Number(row.averageCostPerShare),
    notes: row.notes === null || row.notes === undefined ? null : String(row.notes),
    createdAt: iso(row.createdAt),
    updatedAt: iso(row.updatedAt),
  };
}

async function ensureTables() {
  globalThis.valueSignalUserDataTablesReady ??= pool().query(`
    create table if not exists "watchlist_item" (
      "id" text not null primary key,
      "userId" text not null references "user" ("id") on delete cascade,
      "ticker" text not null,
      "companyName" text not null,
      "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
      "alertEnabled" boolean default true not null,
      "companyEventAlerts" boolean default false not null,
      "industryEventAlerts" boolean default false not null,
      "filingAlerts" boolean default true not null,
      "signalChangeAlerts" boolean default true not null,
      "forecastChangeAlerts" boolean default false not null,
      unique ("userId", "ticker")
    );
    create index if not exists "watchlist_item_userId_idx" on "watchlist_item" ("userId");
    create table if not exists "portfolio_position" (
      "id" text not null primary key,
      "userId" text not null references "user" ("id") on delete cascade,
      "ticker" text not null,
      "companyName" text not null,
      "positionStatus" text not null check ("positionStatus" in ('owned', 'planned')),
      "quantityType" text not null check ("quantityType" in ('shares', 'dollar_amount')),
      "shares" double precision,
      "dollarAmount" double precision,
      "averageCostPerShare" double precision,
      "notes" text,
      "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
      "updatedAt" timestamptz default CURRENT_TIMESTAMP not null,
      check ("shares" is not null or "dollarAmount" is not null),
      check ("shares" is null or "shares" > 0),
      check ("dollarAmount" is null or "dollarAmount" > 0),
      check ("averageCostPerShare" is null or "averageCostPerShare" >= 0)
    );
    create index if not exists "portfolio_position_userId_idx" on "portfolio_position" ("userId");
    create index if not exists "portfolio_position_userId_ticker_idx" on "portfolio_position" ("userId", "ticker");
  `).then(() => undefined);
  return globalThis.valueSignalUserDataTablesReady;
}

export async function assertSupportedStock(ticker: string) {
  const normalized = String(ticker || "").trim().toUpperCase();
  if (!/^[A-Z0-9.-]{1,12}$/.test(normalized)) {
    throw new Error("Ticker is invalid.");
  }

  const stock = await getResearchStock(normalized);
  if (!stock) {
    throw new Error("Ticker is not supported by the current ValueSignal universe.");
  }
  return stock;
}

export async function listWatchlist(userId: string) {
  await ensureTables();
  const result = await pool().query(`select * from "watchlist_item" where "userId" = $1 order by "createdAt" desc`, [userId]);
  return result.rows.map(watchlistFromRow);
}

export async function addWatchlistItem(userId: string, ticker: string) {
  const stock = await assertSupportedStock(ticker);
  await ensureTables();
  const result = await pool().query(
    `insert into "watchlist_item" ("id", "userId", "ticker", "companyName")
     values ($1, $2, $3, $4)
     on conflict ("userId", "ticker") do update set "companyName" = excluded."companyName"
     returning *`,
    [randomUUID(), userId, stock.ticker, stock.companyName],
  );
  return watchlistFromRow(result.rows[0]);
}

export async function updateWatchlistAlerts(userId: string, ticker: string, patch: WatchlistAlertPatch) {
  const allowed = ["alertEnabled", "companyEventAlerts", "industryEventAlerts", "filingAlerts", "signalChangeAlerts", "forecastChangeAlerts"] as const;
  const entries = allowed.filter((key) => typeof patch[key] === "boolean").map((key, index) => ({ key, index }));
  if (!entries.length) throw new Error("No valid alert settings were provided.");
  await ensureTables();
  const assignments = entries.map(({ key, index }) => `"${key}" = $${index + 3}`).join(", ");
  const values = entries.map(({ key }) => patch[key]);
  const result = await pool().query(
    `update "watchlist_item" set ${assignments} where "userId" = $1 and "ticker" = $2 returning *`,
    [userId, ticker.toUpperCase(), ...values],
  );
  return result.rows[0] ? watchlistFromRow(result.rows[0]) : null;
}

export async function removeWatchlistItem(userId: string, ticker: string) {
  await ensureTables();
  const result = await pool().query(`delete from "watchlist_item" where "userId" = $1 and "ticker" = $2`, [userId, ticker.toUpperCase()]);
  return (result.rowCount ?? 0) > 0;
}

function positiveOrNull(value: unknown) {
  if (value === undefined || value === null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : NaN;
}

export function validatePortfolioInput(payload: unknown): PortfolioPositionInput {
  const input = (payload ?? {}) as Record<string, unknown>;
  const ticker = String(input.ticker ?? "").trim().toUpperCase();
  const positionStatus = input.positionStatus === "owned" ? "owned" : "planned";
  const quantityType = input.quantityType === "dollar_amount" ? "dollar_amount" : "shares";
  const shares = positiveOrNull(input.shares);
  const dollarAmount = positiveOrNull(input.dollarAmount);
  const averageCostPerShare = positiveOrNull(input.averageCostPerShare);
  const notes = input.notes === undefined || input.notes === null ? null : String(input.notes).slice(0, 1000);

  if (!ticker) throw new Error("Ticker is required.");
  if (shares !== null && !(shares > 0)) throw new Error("Shares must be greater than zero.");
  if (dollarAmount !== null && !(dollarAmount > 0)) throw new Error("Dollar amount must be greater than zero.");
  if (averageCostPerShare !== null && !(averageCostPerShare >= 0)) throw new Error("Average cost cannot be negative.");
  if (quantityType === "shares" && shares === null) throw new Error("Share-based positions require shares.");
  if (quantityType === "dollar_amount" && dollarAmount === null) throw new Error("Dollar-based positions require a dollar amount.");

  return { ticker, positionStatus, quantityType, shares, dollarAmount, averageCostPerShare, notes };
}

export async function listPortfolio(userId: string) {
  await ensureTables();
  const result = await pool().query(`select * from "portfolio_position" where "userId" = $1 order by "updatedAt" desc`, [userId]);
  return result.rows.map(portfolioFromRow);
}

export async function addPortfolioPosition(userId: string, input: PortfolioPositionInput) {
  const stock = await assertSupportedStock(input.ticker);
  await ensureTables();
  const result = await pool().query(
    `insert into "portfolio_position"
      ("id", "userId", "ticker", "companyName", "positionStatus", "quantityType", "shares", "dollarAmount", "averageCostPerShare", "notes", "updatedAt")
     values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP)
     returning *`,
    [randomUUID(), userId, stock.ticker, stock.companyName, input.positionStatus, input.quantityType, input.shares, input.dollarAmount, input.averageCostPerShare, input.notes],
  );
  return portfolioFromRow(result.rows[0]);
}

export async function updatePortfolioPosition(userId: string, positionId: string, input: PortfolioPositionInput) {
  const stock = await assertSupportedStock(input.ticker);
  await ensureTables();
  const result = await pool().query(
    `update "portfolio_position"
     set "ticker" = $3, "companyName" = $4, "positionStatus" = $5, "quantityType" = $6,
       "shares" = $7, "dollarAmount" = $8, "averageCostPerShare" = $9, "notes" = $10, "updatedAt" = CURRENT_TIMESTAMP
     where "userId" = $1 and "id" = $2
     returning *`,
    [userId, positionId, stock.ticker, stock.companyName, input.positionStatus, input.quantityType, input.shares, input.dollarAmount, input.averageCostPerShare, input.notes],
  );
  return result.rows[0] ? portfolioFromRow(result.rows[0]) : null;
}

export async function removePortfolioPosition(userId: string, positionId: string) {
  await ensureTables();
  const result = await pool().query(`delete from "portfolio_position" where "userId" = $1 and "id" = $2`, [userId, positionId]);
  return (result.rowCount ?? 0) > 0;
}
