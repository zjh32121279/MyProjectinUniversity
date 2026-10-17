import { FeatureIcon } from "@/components/icons/FeatureIcon";
import { cn } from "@/utils/cn";
import type { Tone } from "@/utils/status";

const fallbackThemes: Array<{ tone: Tone; bg: string; text: string }> = [
  { tone: "blue", bg: "from-[#e6f0ff] to-[#f2ecff]", text: "text-[#365a9f]" },
  { tone: "green", bg: "from-[#e8f8ee] to-[#eef9ff]", text: "text-[#26704a]" },
  { tone: "orange", bg: "from-[#fff2dc] to-[#eef7ff]", text: "text-[#9a5a10]" },
  { tone: "purple", bg: "from-[#f1e7ff] to-[#eaf7ff]", text: "text-[#6650b6]" },
  { tone: "cyan", bg: "from-[#e7fbff] to-[#eef3ff]", text: "text-[#13748a]" },
  { tone: "red", bg: "from-[#fff0f2] to-[#eef6ff]", text: "text-[#a1425f]" },
];

function themeForCode(code?: string) {
  const key = String(code ?? "").trim();
  const numeric = Number(key.replace(/\D/g, ""));
  if (Number.isFinite(numeric) && numeric > 0) {
    return fallbackThemes[(numeric - 1) % fallbackThemes.length];
  }
  const hash = key.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return fallbackThemes[hash % fallbackThemes.length];
}

type BookPlaceholderProps = {
  title?: string;
  code?: string;
  categoryCode?: string;
  size?: "sm" | "lg";
  className?: string;
};

export function BookPlaceholder({ title, code, categoryCode, size = "sm", className }: BookPlaceholderProps) {
  const large = size === "lg";
  const theme = themeForCode(categoryCode || code);
  return (
    <div className={cn(large ? `flex h-[86px] w-[62px] shrink-0 flex-col items-center justify-center rounded-2xl bg-gradient-to-br ${theme.bg} text-center shadow-inner` : `flex h-14 w-10 shrink-0 flex-col items-center justify-center rounded-lg bg-gradient-to-br ${theme.bg} text-center shadow-inner`, className)}>
      <FeatureIcon name="available" tone={theme.tone} size="sm" className={large ? "h-8 w-8" : "h-7 w-7"} />
      <span className={large ? `mt-1.5 max-w-[50px] truncate text-[10px] font-bold ${theme.text}` : `mt-0.5 max-w-9 truncate text-[8px] font-bold ${theme.text}`}>{title || code || "Book"}</span>
    </div>
  );
}
