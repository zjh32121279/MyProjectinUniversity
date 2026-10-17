import { ActionButton } from "@/components/ui/ActionButton";

type ErrorStateProps = {
  title?: string;
  description?: string;
  onRetry?: () => void;
};

export function ErrorState({ title = "加载失败", description = "请确认 BookFlow Core 服务已启动，并检查接口返回。", onRetry }: ErrorStateProps) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-[var(--bf-radius-panel)] border border-[#ffd5d5] bg-[#fffafa] p-8 text-center">
      <div className="text-base font-bold text-[var(--bf-danger)]">{title}</div>
      <div className="mt-2 max-w-md text-sm text-[var(--bf-text-secondary)]">{description}</div>
      {onRetry ? (
        <ActionButton className="mt-5" variant="secondary" icon="refresh" onClick={onRetry}>
          重试
        </ActionButton>
      ) : null}
    </div>
  );
}
