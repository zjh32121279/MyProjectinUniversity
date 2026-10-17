import type { PropsWithChildren } from "react";
import { cn } from "@/utils/cn";

export function FilterBar({ children, className }: PropsWithChildren<{ className?: string }>) {
  return <div className={cn("flex flex-wrap items-center gap-3 border-b border-[var(--bf-border-soft)] bg-white px-5 py-5", className)}>{children}</div>;
}

export function FilterSelect(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn("bf-control min-w-[128px] px-3 text-[14px] font-semibold text-[#1b2848]", props.className)} />;
}
