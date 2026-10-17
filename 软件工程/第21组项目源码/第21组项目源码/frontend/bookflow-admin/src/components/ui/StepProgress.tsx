import { cn } from "@/utils/cn";

type StepProgressProps = {
  steps: string[];
  current: number;
  tone?: "blue" | "green" | "orange" | "purple";
};

const toneClass = {
  blue: "bg-[var(--bf-brand)] text-white border-[var(--bf-brand)]",
  green: "bg-[var(--bf-success)] text-white border-[var(--bf-success)]",
  orange: "bg-[var(--bf-warning)] text-white border-[var(--bf-warning)]",
  purple: "bg-[var(--bf-ai)] text-white border-[var(--bf-ai)]",
};

const activeTextClass = {
  blue: "text-[var(--bf-brand)]",
  green: "text-[var(--bf-success)]",
  orange: "text-[var(--bf-warning)]",
  purple: "text-[var(--bf-ai)]",
};

const activeLineClass = {
  blue: "bg-[var(--bf-brand)]",
  green: "bg-[var(--bf-success)]",
  orange: "bg-[var(--bf-warning)]",
  purple: "bg-[var(--bf-ai)]",
};

export function StepProgress({ steps, current, tone = "blue" }: StepProgressProps) {
  return (
    <div className="bf-scrollbar max-w-full overflow-x-auto overflow-y-hidden py-1">
      <div className="flex min-w-max items-center justify-center gap-0">
        {steps.map((step, index) => {
          const active = index <= current;
          return (
            <div key={step} className="flex min-w-[118px] items-center">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full border text-sm font-black",
                  active ? toneClass[tone] : "border-[#a8b5ce] bg-white text-[#1b2848]",
                )}
              >
                {index + 1}
              </div>
              <span className={cn("ml-2 whitespace-nowrap text-sm font-bold", active ? activeTextClass[tone] : "text-[#1b2848]")}>{step}</span>
              {index < steps.length - 1 ? <div className={cn("mx-4 h-px w-10", active ? activeLineClass[tone] : "bg-[#cfd8e8]")} /> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
