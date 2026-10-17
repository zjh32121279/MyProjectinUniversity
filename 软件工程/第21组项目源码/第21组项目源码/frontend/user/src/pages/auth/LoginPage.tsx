import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, UserRound } from "lucide-react";
import { AuthInput } from "@/components/auth/AuthInput";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { userAuthApi } from "@/services/userAuthApi";

export function LoginPage() {
  const navigate = useNavigate();
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage("");
    try {
      await userAuthApi.login({ account: account.trim(), password, remember });
      navigate("/home");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "读者账号服务暂不可用");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <form className="auth-form" onSubmit={handleSubmit}>
        <header className="auth-form__header">
          <h2>登录</h2>
          <p>登录后查看借阅、预约、到期提醒与个性化导读</p>
        </header>

        <div className="auth-form__fields">
          <AuthInput icon={<UserRound size={22} />} value={account} onChange={(event) => setAccount(event.target.value)} placeholder="账号 / 邮箱 / 手机号" autoComplete="username" />
          <PasswordInput value={password} onChange={setPassword} placeholder="密码" autoComplete="current-password" />
        </div>

        <label className="auth-check">
          <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
          <span>
            <Check size={14} />
          </span>
          记住我
        </label>

        {message ? <div className="auth-message">{message}</div> : null}

        <button className="primary-button auth-submit" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "登录中" : "登录"}
        </button>

        <div className="auth-divider">
          <span />
          <em>或</em>
          <span />
        </div>

        <nav className="auth-links" aria-label="登录辅助入口">
          <Link to="/forgot-password">忘记密码？</Link>
          <Link to="/register">立即注册</Link>
          <button type="button" onClick={() => navigate("/home")}>
            游客浏览
          </button>
        </nav>
      </form>
    </AuthLayout>
  );
}
