import { formatDateTime as formatSharedDateTime } from "@common/utils/format";

export function formatDate(value: unknown, fallback = "—") {
  if (!value) return fallback;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value !== "string") return fallback;
  return value.slice(0, 10) || fallback;
}

export function formatDateTime(value: unknown, fallback = "—") {
  const formatted = formatSharedDateTime(value);
  return formatted === "-" ? fallback : formatted;
}

export function maskPhone(value?: string | null) {
  if (!value) return "—";
  return value.replace(/^(\d{3})\d{4}(\d+)/, "$1****$2");
}

export function maskEmail(value?: string | null) {
  if (!value) return "—";
  const [name, domain] = value.split("@");
  if (!name || !domain) return value;
  const visible = name.slice(0, 2);
  return `${visible}${"*".repeat(Math.max(2, name.length - 2))}@${domain}`;
}
