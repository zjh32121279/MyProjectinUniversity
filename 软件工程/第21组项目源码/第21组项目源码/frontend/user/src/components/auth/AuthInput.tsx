import type { InputHTMLAttributes, ReactNode } from "react";

type AuthInputProps = InputHTMLAttributes<HTMLInputElement> & {
  icon: ReactNode;
  action?: ReactNode;
};

export function AuthInput({ icon, action, ...props }: AuthInputProps) {
  return (
    <label className="auth-input">
      <span className="auth-input__icon">{icon}</span>
      <input {...props} />
      {action ? <span className="auth-input__action">{action}</span> : null}
    </label>
  );
}
