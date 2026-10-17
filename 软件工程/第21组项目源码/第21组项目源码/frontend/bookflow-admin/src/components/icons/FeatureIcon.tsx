import AlarmClock from "@icon-park/react/es/icons/AlarmClock";
import Analysis from "@icon-park/react/es/icons/Analysis";
import BookOne from "@icon-park/react/es/icons/BookOne";
import BookOpen from "@icon-park/react/es/icons/BookOpen";
import Bookshelf from "@icon-park/react/es/icons/Bookshelf";
import Calendar from "@icon-park/react/es/icons/Calendar";
import ChartLine from "@icon-park/react/es/icons/ChartLine";
import CheckOne from "@icon-park/react/es/icons/CheckOne";
import Caution from "@icon-park/react/es/icons/Caution";
import Data from "@icon-park/react/es/icons/Data";
import Mail from "@icon-park/react/es/icons/Mail";
import People from "@icon-park/react/es/icons/People";
import Return from "@icon-park/react/es/icons/Return";
import Robot from "@icon-park/react/es/icons/Robot";
import Setting from "@icon-park/react/es/icons/Setting";
import type { ComponentType } from "react";
import type { IIconProps } from "@icon-park/react/es/runtime";
import { cn } from "@/utils/cn";
import type { Tone } from "@/utils/status";

const iconMap = {
  borrow: BookOpen,
  return: Return,
  readers: People,
  overdue: AlarmClock,
  catalog: Bookshelf,
  available: BookOne,
  reservation: Calendar,
  ai: Robot,
  risk: Caution,
  success: CheckOne,
  notification: Mail,
  data: Data,
  analysis: Analysis,
  trend: ChartLine,
  settings: Setting,
} satisfies Record<string, ComponentType<IIconProps>>;

const toneColors: Record<Tone, [string, string, string, string]> = {
  blue: ["#2563EB", "#DBEAFE", "#93C5FD", "#1D4ED8"],
  green: ["#16A34A", "#DCFCE7", "#86EFAC", "#15803D"],
  orange: ["#F59E0B", "#FFEDD5", "#FDBA74", "#EA580C"],
  red: ["#EF4444", "#FEE2E2", "#FCA5A5", "#DC2626"],
  purple: ["#7C3AED", "#F3E8FF", "#C4B5FD", "#6D28D9"],
  cyan: ["#0891B2", "#ECFEFF", "#67E8F9", "#0E7490"],
  gray: ["#64748B", "#F1F5F9", "#CBD5E1", "#475569"],
};

export type FeatureIconName = keyof typeof iconMap;

type FeatureIconProps = {
  name: FeatureIconName | string;
  tone?: Tone;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
};

export function FeatureIcon({ name, tone = "blue", size = "md", className }: FeatureIconProps) {
  const Icon = iconMap[name as FeatureIconName] ?? Data;
  const pixelSize = size === "xl" ? 38 : size === "lg" ? 34 : size === "sm" ? 22 : 28;
  const boxSize = size === "xl" ? "h-20 w-20" : size === "lg" ? "h-16 w-16" : size === "sm" ? "h-10 w-10" : "h-14 w-14";

  return (
    <span className={cn("inline-flex shrink-0 items-center justify-center rounded-full", boxSize, className)} style={{ backgroundColor: toneColors[tone][1] }}>
      <Icon theme="multi-color" size={pixelSize} fill={toneColors[tone]} strokeWidth={3} />
    </span>
  );
}
