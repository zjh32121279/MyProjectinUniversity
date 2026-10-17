type StepIndicatorProps = {
  steps: string[];
  current: number;
};

export function StepIndicator({ steps, current }: StepIndicatorProps) {
  return (
    <div className="step-indicator" aria-label="找回密码进度">
      {steps.map((step, index) => {
        const stepNo = index + 1;
        const active = stepNo === current;
        return (
          <div className="step-indicator__item" key={step}>
            <span className={active ? "is-active" : ""}>{stepNo}</span>
            <strong className={active ? "is-active" : ""}>{step}</strong>
            {index < steps.length - 1 ? <i /> : null}
          </div>
        );
      })}
    </div>
  );
}
