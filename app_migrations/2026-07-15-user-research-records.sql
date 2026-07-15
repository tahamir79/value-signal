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

