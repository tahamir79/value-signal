import { isPublicPreviewTicker } from "@/lib/public-universe";
import type { Entitlement } from "@/types/billing";
import type { StockRecord } from "@/types/stock";

const FREE_UNDERVALUED_LIMIT = 3;
const FREE_GROWTH_LIMIT = 3;

export function isGrowthTeaser(stock: StockRecord) {
  return stock.growthSpurt?.status === "detected" || stock.growthSpurt?.status === "emerging";
}

export function isUndervaluedTeaser(stock: StockRecord) {
  return stock.signal === "potentially-undervalued";
}

export function selectAccessibleStocks(records: StockRecord[], entitlement: Entitlement) {
  if (entitlement.accessLevel === "pro") {
    return {
      records,
      lockedCount: 0,
      previewCount: records.length,
      freeUndervaluedCount: records.filter(isUndervaluedTeaser).length,
      freeGrowthCount: records.filter(isGrowthTeaser).length,
    };
  }

  if (entitlement.accessLevel === "public") {
    const preview = records.filter((stock) => isPublicPreviewTicker(stock.ticker));
    return {
      records: preview,
      lockedCount: Math.max(0, records.length - preview.length),
      previewCount: preview.length,
      freeUndervaluedCount: 0,
      freeGrowthCount: 0,
    };
  }

  const selected = new Map<string, StockRecord>();
  for (const stock of records) {
    if (isPublicPreviewTicker(stock.ticker)) selected.set(stock.ticker, stock);
  }
  const undervalued = records.filter((stock) => !selected.has(stock.ticker) && isUndervaluedTeaser(stock)).slice(0, FREE_UNDERVALUED_LIMIT);
  for (const stock of undervalued) selected.set(stock.ticker, stock);
  const growth = records.filter((stock) => !selected.has(stock.ticker) && isGrowthTeaser(stock)).slice(0, FREE_GROWTH_LIMIT);
  for (const stock of growth) selected.set(stock.ticker, stock);

  return {
    records: records.filter((stock) => selected.has(stock.ticker)),
    lockedCount: Math.max(0, records.length - selected.size),
    previewCount: selected.size,
    freeUndervaluedCount: undervalued.length,
    freeGrowthCount: growth.length,
  };
}

export function canAccessStock(ticker: string, records: StockRecord[], entitlement: Entitlement) {
  if (entitlement.accessLevel === "pro") return true;
  return selectAccessibleStocks(records, entitlement).records.some((stock) => stock.ticker.toUpperCase() === ticker.toUpperCase());
}
