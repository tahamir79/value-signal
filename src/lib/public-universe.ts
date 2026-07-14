export const PUBLIC_PREVIEW_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "JNJ", "XOM", "F", "KO", "INTC"] as const;

export function isPublicPreviewTicker(ticker: string) {
  return (PUBLIC_PREVIEW_TICKERS as readonly string[]).includes(ticker.toUpperCase());
}
