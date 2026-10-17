export function formatNumber(value: unknown, fallback = "0") {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return fallback;
  return new Intl.NumberFormat("zh-CN").format(numeric);
}

export function formatPercent(value: unknown, digits = 1) {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return "-";
  const normalized = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
  return `${normalized.toFixed(digits)}%`;
}

export function formatDateTime(value: unknown) {
  if (!value || typeof value !== "string") return "-";
  return value.replace("T", " ").slice(0, 16);
}

export function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function getNumber(record: Record<string, unknown> | undefined, key: string, fallback = 0) {
  const value = record?.[key];
  return typeof value === "number" ? value : Number(value ?? fallback);
}
