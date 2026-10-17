import type { ReactNode } from "react";

type StatCardProps = {
  icon: ReactNode;
  label: string;
  value: number | string | null | undefined;
  unit?: string;
  tone?: "blue" | "orange" | "green" | "red" | "purple";
};

export function StatCard({ icon, label, value, unit, tone = "blue" }: StatCardProps) {
  return (
    <div className={`stat-card stat-card--${tone}`}>
      <span className="stat-card__icon">{icon}</span>
      <div>
        <p>{label}</p>
        <strong>
          {value ?? "—"}
          {unit ? <small>{unit}</small> : null}
        </strong>
      </div>
    </div>
  );
}
