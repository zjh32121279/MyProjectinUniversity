import { cn } from "@/utils/cn";
import { labelForStatus, toneForStatus, type Tone } from "@/utils/status";

type StatusBadgeProps = {
  value: unknown;
  tone?: Tone;
  className?: string;
};

const toneClass: Record<Tone, string> = {
  blue: "bg-[#eaf2ff] text-[#1456dc]",
  green: "bg-[#e8f8ee] text-[#13833d]",
  orange: "bg-[#fff3dc] text-[#b85f00]",
  red: "bg-[#fee9e9] text-[#dc2626]",
  purple: "bg-[#f1eaff] text-[#6d28d9]",
  cyan: "bg-[#e7fbff] text-[#087990]",
  gray: "bg-[#f1f5f9] text-[#64748b]",
};

export function StatusBadge({ value, tone, className }: StatusBadgeProps) {
  const resolvedTone = tone ?? toneForStatus(value);
  return (
    <span className={cn("inline-flex items-center rounded-[var(--bf-radius-badge)] px-2.5 py-1 text-xs font-bold", toneClass[resolvedTone], className)}>
      {labelForStatus(value)}
    </span>
  );
}
