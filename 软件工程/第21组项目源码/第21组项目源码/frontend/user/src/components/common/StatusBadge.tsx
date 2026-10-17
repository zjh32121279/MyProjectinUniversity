import { statusText } from "@/utils/statusText";

type StatusBadgeProps = {
  status?: string | null;
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`status-badge status-badge--${status || "unknown"}`}>{statusText(status)}</span>;
}
