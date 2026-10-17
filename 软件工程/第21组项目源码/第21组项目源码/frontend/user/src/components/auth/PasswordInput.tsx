import { useState } from "react";
import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { AuthInput } from "@/components/auth/AuthInput";

type PasswordInputProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  autoComplete?: string;
};

export function PasswordInput({ value, onChange, placeholder, autoComplete }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <AuthInput
      icon={<LockKeyhole size={22} />}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      type={visible ? "text" : "password"}
      autoComplete={autoComplete}
      action={
        <button type="button" className="auth-icon-button" onClick={() => setVisible((current) => !current)} aria-label={visible ? "隐藏密码" : "显示密码"}>
          {visible ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      }
    />
  );
}
