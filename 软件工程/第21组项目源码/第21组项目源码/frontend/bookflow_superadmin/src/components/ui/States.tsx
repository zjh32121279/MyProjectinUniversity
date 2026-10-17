export function SkeletonBlock({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-[12px] bg-gradient-to-r from-[#eef3fb] via-[#f8fbff] to-[#eef3fb] ${className ?? ""}`} />;
}

export function ErrorState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="rounded-[12px] border border-[#ffd5d5] bg-[#fffafa] p-8 text-center shadow-sm">
        <div className="text-base font-black text-[#ef4444]">加载失败</div>
        <div className="mt-2 text-sm font-semibold text-[#64718d]">请确认 BookFlow Core 服务已启动，并检查接口返回。</div>
        {onRetry ? (
          <button className="mt-5 rounded-[8px] border border-[#dce4f2] bg-white px-4 py-2 text-sm font-black text-[#1769f7]" onClick={onRetry} type="button">
            重试
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function CompactEmpty({ label = "暂无数据" }: { label?: string }) {
  return <div className="bf-super-empty-compact">{label}</div>;
}
