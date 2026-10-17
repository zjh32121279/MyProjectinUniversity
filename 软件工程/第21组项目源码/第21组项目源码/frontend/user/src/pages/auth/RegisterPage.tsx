import { useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate } from "react-router-dom";
import { Check, Mail, Phone, ShieldCheck, UserRound, X } from "lucide-react";
import { AuthInput } from "@/components/auth/AuthInput";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { userAuthApi } from "@/services/userAuthApi";

const TERMS_ITEMS = [
  { label: "读者类型", value: "本馆按读者类型（儿童、青少年、成人、老年、机构）分别设置最大可借册数、借阅天数与续借次数，具体数值以普管端「流通规则」为准" },
  { label: "热门与冷门", value: "近 90 天借阅或预约达到阈值的图书标记为「热门」，缩短借期；近 365 天低借阅且长期未流通的标记为「冷门」，可正常借阅" },
  { label: "预约取书", value: "无可用副本时读者可提交预约，到书后系统发送通知，保留取书期限以流通策略中的预约保留天数为准，超时未取自动取消" },
  { label: "逾期暂停", value: "任一借阅逾期未还期间，账号自动暂停借阅权限，归还所有逾期图书后即时恢复" },
  { label: "信用分", value: "系统依据借阅归还及时性、逾期次数与严重程度自动计算读者信用分，信用分过低可能影响借阅额度" },
  { label: "行为规范", value: "读者须使用本人真实身份注册登录，妥善保管账号密码，不得转借、转让或利用本系统从事违法违规活动" },
  { label: "服务变更", value: "系统升级维护可能短暂影响访问，流通规则变更将在通知中心提前公告，重大调整须经馆员审批后生效" },
];

const PRIVACY_ITEMS = [
  { label: "收集内容", value: "注册与登录所需的姓名与读者证号，借阅与预约产生的业务记录，通知投递所需的联系方式（手机号或邮箱）" },
  { label: "手机号保护", value: "完整手机号经哈希处理后存储，读者端仅展示掩码（如 138****1234），馆员端经授权方可查看脱敏值" },
  { label: "数据存储", value: "所有数据存储于馆内或指定服务器，借阅与预约记录保留至还书或取消后不少于 2 年，日志定期归档" },
  { label: "安全措施", value: "登录密码加密存储（SHA-256 + 盐值），API 传输强制 HTTPS，数据库访问基于角色权限控制，关键操作写入审计日志" },
  { label: "第三方接入", value: "本系统未集成第三方统计或广告 SDK，不向馆外机构共享、转让或公开披露读者个人信息" },
  { label: "用户权利", value: "读者可在个人中心更新联系方式与通知偏好，可申请查询、更正或删除个人信息，可随时注销账号" },
  { label: "政策更新", value: "隐私政策如有重大变更，将在系统通知中心以消息形式推送，并在登录页公示更新日期" },
];

function PolicyModal({ title, items, onClose }: { title: string; items: { label: string; value: string }[]; onClose: () => void }) {
  return createPortal(
    <div className="reader-detail-dialog" role="dialog" aria-modal="true" aria-label={title} style={{ zIndex: 300 }}>
      <div className="reader-detail-dialog__backdrop" onClick={onClose} />
      <div className="reader-detail-dialog__panel" style={{ width: "min(680px, calc(100vw - 40px))", maxHeight: "min(640px, calc(100vh - 48px))", overflowY: "auto" }}>
        <div className="reader-detail-dialog__header">
          <div>{title}</div>
          <button type="button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </div>
        <div className="profile-detail-text">
          {items.map((item, index) => (
            <p key={index}>
              <strong>{item.label}</strong>
              <span>{item.value}</span>
            </p>
          ))}
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", phone: "", code: "", password: "", confirmPassword: "" });
  const [accepted, setAccepted] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [policyModal, setPolicyModal] = useState<"terms" | "privacy" | null>(null);

  function updateField(name: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage("");
    try {
      await userAuthApi.register({ ...form, accepted });
      setMessage("注册成功，正在进入读者首页");
      navigate("/home");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "注册失败，请检查填写信息");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCode() {
    const account = form.phone || form.email;
    if (!account) {
      setMessage("请先填写手机号或邮箱");
      return;
    }
    try {
      const result = await userAuthApi.requestVerificationCode(account, "register");
      setMessage(result.debug_code ? `验证码已生成：${result.debug_code}（本地调试环境使用）` : "验证码已发送，请注意查收");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "验证码生成失败");
    }
  }

  return (
    <AuthLayout>
      <form className="auth-form auth-form--compact" onSubmit={handleSubmit}>
        <header className="auth-form__header">
          <h2>注册</h2>
          <p>创建 BookFlow 读者账号，开启借阅、预约与个性化阅读服务</p>
        </header>

        <div className="auth-form__fields auth-form__fields--compact">
          <AuthInput icon={<UserRound size={21} />} value={form.name} onChange={(event) => updateField("name", event.target.value)} placeholder="姓名" autoComplete="name" />
          <AuthInput icon={<Mail size={21} />} value={form.email} onChange={(event) => updateField("email", event.target.value)} placeholder="邮箱" autoComplete="email" />
          <AuthInput icon={<Phone size={21} />} value={form.phone} onChange={(event) => updateField("phone", event.target.value)} placeholder="手机号" autoComplete="tel" />
          <AuthInput
            icon={<ShieldCheck size={21} />}
            value={form.code}
            onChange={(event) => updateField("code", event.target.value)}
            placeholder="验证码"
            action={
              <button type="button" className="auth-code-button" onClick={handleCode}>
                获取验证码
              </button>
            }
          />
          <PasswordInput value={form.password} onChange={(value) => updateField("password", value)} placeholder="设置密码" autoComplete="new-password" />
          <PasswordInput value={form.confirmPassword} onChange={(value) => updateField("confirmPassword", value)} placeholder="确认密码" autoComplete="new-password" />
        </div>

        <label className="auth-check">
          <input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
          <span>
            <Check size={14} />
          </span>
          我已阅读并同意
          <button type="button" className="auth-check__link" onClick={() => setPolicyModal("terms")}>《服务条款》</button>
          <button type="button" className="auth-check__link" onClick={() => setPolicyModal("privacy")}>《隐私政策》</button>
        </label>

        {message ? <div className="auth-message">{message}</div> : null}

        <button className="primary-button auth-submit auth-submit--compact" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "注册中" : "注册"}
        </button>

        <div className="auth-divider auth-divider--compact">
          <span />
          <em>或</em>
          <span />
        </div>

        <nav className="auth-links auth-links--register" aria-label="注册辅助入口">
          <Link to="/login">返回登录</Link>
          <button type="button" onClick={() => navigate("/home")}>
            游客浏览
          </button>
          <Link to="/login">已有账号？去登录</Link>
        </nav>
      </form>

      {policyModal ? (
        <PolicyModal
          title={policyModal === "terms" ? "服务条款" : "隐私政策"}
          items={policyModal === "terms" ? TERMS_ITEMS : PRIVACY_ITEMS}
          onClose={() => setPolicyModal(null)}
        />
      ) : null}
    </AuthLayout>
  );
}
