import type { InputHTMLAttributes } from "react";
import { AppIcon } from "@/components/icons/AppIcon";
import { cn } from "@/utils/cn";

type SearchInputProps = InputHTMLAttributes<HTMLInputElement>;

export function SearchInput({ className, ...props }: SearchInputProps) {
  return (
    <label className={cn("bf-control flex items-center gap-2.5 px-4", className)}>
      <input className="min-w-0 flex-1 border-0 bg-transparent text-[15px] outline-none placeholder:text-[#8b99b2]" {...props} />
      <AppIcon name="search" size={20} className="text-[#53627f]" />
    </label>
  );
}
