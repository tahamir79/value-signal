const WINDOWS_RESERVED_FILENAMES = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  ...Array.from({ length: 9 }, (_, index) => `COM${index + 1}`),
  ...Array.from({ length: 9 }, (_, index) => `LPT${index + 1}`),
]);

export function tickerArtifactStem(ticker: string) {
  const normalized = ticker.toUpperCase().trim();
  const safe = normalized
    .replace(/[^A-Z0-9._-]/g, "-")
    .replace(/[ .]+$/g, "") || "UNKNOWN";
  return WINDOWS_RESERVED_FILENAMES.has(safe.split(".")[0]) ? `_${safe}` : safe;
}
