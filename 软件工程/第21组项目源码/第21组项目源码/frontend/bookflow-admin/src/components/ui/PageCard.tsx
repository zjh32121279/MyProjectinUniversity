import type { PropsWithChildren, ReactNode } from "react";
import { cn } from "@/utils/cn";

type PageCardProps = PropsWithChildren<{
  title?: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
}>;

export function PageCard({ title, description, actions, className, bodyClassName, children }: PageCardProps) {
  return (
    <section className={cn("bf-card overflow-hidden", className)}>
      {(title || description || actions) && (
        <div className="flex items-start justify-between gap-4 border-b border-[var(--bf-border-soft)] px-7 py-6">
          <div>
            {title ? <h2 className="text-[22px] font-bold text-[#071334]">{title}</h2> : null}
            {description ? <p className="mt-1 text-sm text-[var(--bf-text-secondary)]">{description}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </div>
      )}
      <div className={cn("p-7", bodyClassName)}>{children}</div>
    </section>
  );
}
