import type { ButtonHTMLAttributes, ReactNode } from "react";
import { AppIcon, type AppIconName } from "@/components/icons/AppIcon";
import { cn } from "@/utils/cn";

type ActionButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success" | "warning" | "purple";
  size?: "sm" | "md" | "lg";
  icon?: AppIconName;
  children?: ReactNode;
};

const variants = {
  primary: "bg-[var(--bf-brand)] text-white shadow-[0_10px_20px_rgba(37,99,235,0.18)] hover:bg-[var(--bf-brand-hover)]",
  secondary: "border border-[#dce4f2] bg-white text-[#0f1b3d] hover:bg-[#f7faff]",
  ghost: "text-[var(--bf-brand)] hover:bg-[var(--bf-brand-soft)]",
  danger: "bg-[var(--bf-danger)] text-white hover:bg-[#dc2626]",
  success: "bg-[var(--bf-success)] text-white hover:bg-[#15803d]",
  warning: "bg-[var(--bf-warning)] text-white hover:bg-[#d97706]",
  purple: "bg-[var(--bf-ai)] text-white hover:bg-[#6d28d9]",
};

const sizes = {
  sm: "h-9 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export function ActionButton({ className, variant = "primary", size = "md", icon, children, disabled, ...props }: ActionButtonProps) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[var(--bf-radius-control)] font-semibold transition disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      disabled={disabled}
      {...props}
    >
      {icon ? <AppIcon name={icon} size={16} /> : null}
      {children}
    </button>
  );
}
