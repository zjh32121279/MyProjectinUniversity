import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck, UserRound } from "lucide-react";
import { AuthInput } from "@/components/auth/AuthInput";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { StepIndicator } from "@/components/auth/StepIndicator";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { userAuthApi } from "@/services/userAuthApi";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ account: "", code: "", password: "", confirmPassword: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  function updateField(name: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage("");
    try {
      await userAuthApi.resetPassword(form);
      setMessage("密码已重置，请使用新密码登录");
      navigate("/login");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "重置失败，请检查验证码和新密码");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCode() {
    if (!form.account) {
      setMessage("请先填写手机号、邮箱或读者编号");
      return;
    }
    try {
      const result = await userAuthApi.requestVerificationCode(form.account, "reset_password");
      setMessage(result.debug_code ? `验证码已生成：${result.debug_code}（本地调试环境使用）` : "验证码已发送，请注意查收");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "验证码生成失败");
    }
  }

  return (
    <AuthLayout>
      <form className="auth-form auth-form--recover" onSubmit={handleSubmit}>
        <header className="auth-form__header">
          <h2>找回密码</h2>
          <p>通过绑定手机号或邮箱重置你的 BookFlow 账号密码</p>
        </header>

        <StepIndicator steps={["验证身份", "重置密码", "完成"]} current={1} />

        <div className="auth-form__fields">
          <AuthInput icon={<UserRound size={22} />} value={form.account} onChange={(event) => updateField("account", event.target.value)} placeholder="手机号 / 邮箱" autoComplete="username" />
          <AuthInput
            icon={<ShieldCheck size={22} />}
            value={form.code}
            onChange={(event) => updateField("code", event.target.value)}
            placeholder="验证码"
            action={
              <button type="button" className="auth-code-button" onClick={handleCode}>
                获取验证码
              </button>
            }
          />
          <PasswordInput value={form.password} onChange={(value) => updateField("password", value)} placeholder="新密码" autoComplete="new-password" />
          <PasswordInput value={form.confirmPassword} onChange={(value) => updateField("confirmPassword", value)} placeholder="确认新密码" autoComplete="new-password" />
        </div>

        {message ? <div className="auth-message">{message}</div> : null}

        <button className="primary-button auth-submit" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "重置中" : "重置密码"}
        </button>

        <div className="auth-divider">
          <span />
          <em>或</em>
          <span />
        </div>

        <nav className="auth-links auth-links--two" aria-label="找回密码辅助入口">
          <Link to="/login">返回登录</Link>
          <Link to="/register">立即注册</Link>
        </nav>
      </form>
    </AuthLayout>
  );
}
