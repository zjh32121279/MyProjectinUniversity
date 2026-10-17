import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

type GlassCardProps = {
  children: ReactNode;
  className?: string;
};

export function GlassCard({ children, className }: GlassCardProps) {
  return <section className={cn("user-card glass-panel", className)}>{children}</section>;
}
