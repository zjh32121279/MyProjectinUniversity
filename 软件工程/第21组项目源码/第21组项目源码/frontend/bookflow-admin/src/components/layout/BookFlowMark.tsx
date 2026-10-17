import { cn } from "@/utils/cn";

function LogoGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true" className={cn("block", className)} fill="none">
      <defs>
        <linearGradient id="bookflow-logo-gradient" x1="8" y1="6" x2="32" y2="34" gradientUnits="userSpaceOnUse">
          <stop stopColor="#3B82F6" />
          <stop offset="1" stopColor="#2563EB" />
        </linearGradient>
      </defs>
      <rect x="5" y="5" width="30" height="30" rx="9" fill="url(#bookflow-logo-gradient)" />
      <path
        d="M11.5 13.25c0-1.1.9-2 2-2h5.25c1.1 0 2 .9 2 2v15.5c0-1.1-.9-2-2-2H13.5c-1.1 0-2-.9-2-2v-11.5Z"
        fill="white"
        opacity="0.96"
      />
      <path
        d="M28.5 13.25c0-1.1-.9-2-2-2h-5.25c-1.1 0-2 .9-2 2v15.5c0-1.1.9-2 2-2h5.25c1.1 0 2-.9 2-2v-11.5Z"
        fill="white"
        opacity="0.96"
      />
      <path d="M20 12.4v15.8" stroke="#2563EB" strokeWidth="1.8" strokeLinecap="round" opacity="0.8" />
      <path d="M14.6 16h3.2M14.6 19.7h3.2M25.4 16h-3.2M25.4 19.7h-3.2" stroke="#2563EB" strokeWidth="1.45" strokeLinecap="round" opacity="0.45" />
    </svg>
  );
}

export function BookFlowMark({ compact = false, variant = "inline" }: { compact?: boolean; variant?: "inline" | "stacked" }) {
  if (variant === "stacked") {
    return (
      <div className="flex flex-col items-center">
        <span className="flex h-24 w-24 items-center justify-center drop-shadow-[0_18px_32px_rgba(37,99,235,0.18)]">
          <LogoGlyph className="h-20 w-20" />
        </span>
        <span className="bf-brand-word mt-3 text-[48px] font-black leading-none tracking-[-0.04em] text-[#111827]">BookFlow</span>
      </div>
    );
  }

  return (
    <div className={cn("flex min-w-0 select-none items-center gap-3", compact ? "w-full justify-center" : "w-full")} aria-label="BookFlow" style={{ WebkitUserSelect: "none", userSelect: "none" }}>
      <span className="flex h-10 w-10 shrink-0 items-center justify-center">
        <LogoGlyph className="h-8 w-8 drop-shadow-[0_8px_16px_rgba(37,99,235,0.14)]" />
      </span>
      {!compact ? (
        <span className="bf-brand-word min-w-0 whitespace-nowrap text-[24px] font-black leading-none tracking-[-0.035em] text-[#111827]">BookFlow</span>
      ) : null}
    </div>
  );
}
