import { FeatureIcon } from "@/components/icons/FeatureIcon";

type EmptyStateProps = {
  title?: string;
  description?: string;
};

export function EmptyState({ title = "暂无数据", description = "接口当前没有返回可展示的记录。" }: EmptyStateProps) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-[var(--bf-radius-panel)] border border-dashed border-[#d8e1ef] bg-[#fbfdff] p-8 text-center">
      <FeatureIcon name="data" tone="gray" />
      <div className="mt-4 text-base font-bold text-[#12203f]">{title}</div>
      <div className="mt-2 max-w-md text-sm text-[var(--bf-text-secondary)]">{description}</div>
    </div>
  );
}
