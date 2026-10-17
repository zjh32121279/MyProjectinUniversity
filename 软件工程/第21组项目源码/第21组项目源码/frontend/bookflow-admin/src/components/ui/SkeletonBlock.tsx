import { cn } from "@/utils/cn";

export function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-[var(--bf-radius-panel)] bg-gradient-to-r from-[#eef3fb] via-[#f8fbff] to-[#eef3fb]", className)} />;
}

export function TableSkeleton() {
  return (
    <div className="space-y-3 p-6">
      {Array.from({ length: 6 }).map((_, index) => (
        <SkeletonBlock key={index} className="h-14" />
      ))}
    </div>
  );
}
