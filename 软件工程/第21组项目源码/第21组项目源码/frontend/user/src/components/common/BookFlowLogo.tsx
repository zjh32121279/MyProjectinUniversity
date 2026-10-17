import { BookOpenText } from "lucide-react";
import { cn } from "@/utils/cn";

type BookFlowLogoProps = {
  compact?: boolean;
  className?: string;
};

export function BookFlowLogo({ compact = false, className }: BookFlowLogoProps) {
  return (
    <div className={cn("bookflow-logo", compact && "bookflow-logo--compact", className)}>
      <span className="bookflow-logo__mark">
        <BookOpenText size={compact ? 28 : 58} strokeWidth={2.3} />
      </span>
      <span className="bookflow-logo__text">
        <strong>BookFlow</strong>
        {!compact ? <small>智慧阅读 · 流动书香</small> : null}
      </span>
    </div>
  );
}
