import { FeatureIcon, type FeatureIconName } from "@/components/icons/FeatureIcon";
import { cn } from "@/utils/cn";
import type { Tone } from "@/utils/status";

type StatCardProps = {
  title: string;
  value: string | number;
  unit?: string;
  icon: FeatureIconName | string;
  tone?: Tone;
  trend?: string;
  className?: string;
  compact?: boolean;
};

export function StatCard({ title, value, unit, icon, tone = "blue", trend, className, compact }: StatCardProps) {
  if (compact) {
    return (
      <div className={cn("bf-card flex h-[108px] min-h-[108px] items-center px-5 py-4", className)}>
        <div className="flex w-full items-center gap-3">
          <FeatureIcon name={icon} tone={tone} size="md" />
          <div className="min-w-0">
            <div className="text-sm font-semibold text-[#17213c]">{title}</div>
            <div className="mt-0.5 flex items-baseline gap-1.5">
              <span className="whitespace-nowrap text-[30px] font-black leading-none text-[#071334]">{value}</span>
              {unit ? <span className="text-sm font-semibold text-[#17213c]">{unit}</span> : null}
            </div>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className={cn("bf-card min-h-[152px] px-7 py-6", className)}>
      <div className="flex items-center gap-4">
        <FeatureIcon name={icon} tone={tone} size="lg" />
        <div className="text-[17px] font-semibold text-[#17213c]">{title}</div>
      </div>
      <div className="mt-5 flex min-w-0 items-end gap-2">
        <span className="whitespace-nowrap text-[34px] font-black leading-none tracking-normal text-[#071334]">{value}</span>
        {unit ? <span className="pb-1 text-base font-semibold text-[#17213c]">{unit}</span> : null}
      </div>
      {trend ? <div className="mt-3 text-sm text-[var(--bf-text-secondary)]">{trend}</div> : null}
    </div>
  );
}
