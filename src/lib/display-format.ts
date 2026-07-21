const DISPLAY_DATE_FORMATTER = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

export function formatDisplayDate(value: string | null | undefined) {
  if (!value) return "Unavailable";
  const trimmed = value.trim();
  if (!trimmed) return "Unavailable";
  const date = /^\d{4}-\d{2}-\d{2}$/.test(trimmed)
    ? new Date(`${trimmed}T00:00:00.000Z`)
    : new Date(trimmed);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return DISPLAY_DATE_FORMATTER.format(date);
}

function trimFixed(value: number, digits: number) {
  return value.toFixed(digits).replace(/\.?0+$/, "");
}

export function formatShareQuantity(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  const absolute = Math.abs(value);
  if (Number.isInteger(value)) return value.toLocaleString();
  if (absolute < 1) return value.toFixed(4);
  if (absolute < 10) return value.toFixed(3);
  return trimFixed(value, 2);
}
