type FlowFeedbackProps = {
  message?: string;
};

export function FlowFeedback({ message }: FlowFeedbackProps) {
  if (!message) return null;
  return <div className="flow-feedback" role="status">{message}</div>;
}
