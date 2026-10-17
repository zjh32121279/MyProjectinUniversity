import type { FormEvent } from "react";
import { X } from "lucide-react";
import type { ProfileCenterAction, ProfileCenterSection, ReaderProfile } from "@/types/user";
import { display } from "./profileSections";

export function ProfileDetailDialog({
  section,
  onClose,
  ...props
}: {
  section: ProfileCenterSection | null;
  onClose: () => void;
} & Omit<ProfileDetailCardProps, "section">) {
  if (!section) return null;
  return (
    <div className="profile-detail-dialog" role="dialog" aria-modal="true" aria-label={section.title}>
      <div className="profile-detail-dialog__backdrop" onClick={onClose} />
      <div className="profile-detail-dialog__panel">
        <button className="profile-detail-dialog__close" type="button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        <ProfileDetailCard section={section} {...props} />
      </div>
    </div>
  );
}

type ProfileDetailCardProps = {
  section: ProfileCenterSection | null;
  profile?: ReaderProfile | null;
  onAction: (action: ProfileCenterAction) => void;
  onContactSubmit: (body: { phone?: string; email?: string }) => void;
  contactPending: boolean;
  onPasswordSubmit: (body: { old_password: string; new_password: string; confirm_password: string }) => void;
  passwordPending: boolean;
  onFeedbackSubmit: (body: { category?: string; content: string }) => void;
  feedbackPending: boolean;
};

function ProfileDetailCard({
  section,
  profile,
  onAction,
  onContactSubmit,
  contactPending,
  onPasswordSubmit,
  passwordPending,
  onFeedbackSubmit,
  feedbackPending,
}: ProfileDetailCardProps) {
  if (!section) {
    return (
      <section className="profile-detail-card">
        <h2>个人中心详情</h2>
        <p>请选择左侧入口查看详细内容。</p>
      </section>
    );
  }
  return (
    <section className="profile-detail-card">
      <div className="profile-detail-card__header">
        <div>
          <h2>{section.title}</h2>
          <p>{section.summary}</p>
        </div>
        <span>{section.group}</span>
      </div>
      {section.group === "关于我们" ? (
        <div className="profile-detail-text">
          {section.items.map((item, index) => (
            <p key={index}>
              <strong>{item.label}</strong>
              <span>{display(item.value)}</span>
            </p>
          ))}
        </div>
      ) : (
        <div className="profile-detail-list">
          {section.items.map((item, index) => (
            <article key={`${item.label}-${index}`}>
              <span>{item.label}</span>
              <strong>{display(item.value)}</strong>
              {item.description ? <em>{item.description}</em> : null}
            </article>
          ))}
        </div>
      )}
      <div className="profile-detail-actions">
        {section.actions.map((action) => {
          if (action.type === "contact_form") return <ContactForm key={action.label} profile={profile} pending={contactPending} onSubmit={onContactSubmit} />;
          if (action.type === "password_form") return <PasswordForm key={action.label} pending={passwordPending} onSubmit={onPasswordSubmit} />;
          if (action.type === "feedback_form") return <FeedbackForm key={action.label} pending={feedbackPending} onSubmit={onFeedbackSubmit} />;
          return <button key={action.label} type="button" onClick={() => onAction(action)}>{action.label}</button>;
        })}
      </div>
    </section>
  );
}

function ContactForm({ profile, pending, onSubmit }: { profile?: ReaderProfile | null; pending: boolean; onSubmit: (body: { phone?: string; email?: string }) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({ phone: display(form.get("phone"), ""), email: display(form.get("email"), "") });
  }
  return (
    <form className="profile-inline-form" onSubmit={submit}>
      <input name="phone" defaultValue={display(profile?.phone_masked, "")} placeholder="手机号" />
      <input name="email" defaultValue={display(profile?.email, "")} placeholder="邮箱" />
      <button type="submit" disabled={pending}>{pending ? "保存中" : "保存联系方式"}</button>
    </form>
  );
}

function PasswordForm({ pending, onSubmit }: { pending: boolean; onSubmit: (body: { old_password: string; new_password: string; confirm_password: string }) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({
      old_password: display(form.get("old_password"), ""),
      new_password: display(form.get("new_password"), ""),
      confirm_password: display(form.get("confirm_password"), ""),
    });
  }
  return (
    <form className="profile-inline-form" onSubmit={submit}>
      <input name="old_password" type="password" placeholder="当前密码" />
      <input name="new_password" type="password" placeholder="新密码" />
      <input name="confirm_password" type="password" placeholder="确认新密码" />
      <button type="submit" disabled={pending}>{pending ? "修改中" : "修改密码"}</button>
    </form>
  );
}

function FeedbackForm({ pending, onSubmit }: { pending: boolean; onSubmit: (body: { category?: string; content: string }) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({ category: display(form.get("category"), "general"), content: display(form.get("content"), "") });
    event.currentTarget.reset();
  }
  return (
    <form className="profile-inline-form profile-inline-form--feedback" onSubmit={submit}>
      <select name="category" defaultValue="general">
        <option value="general">普通反馈</option>
        <option value="bug">问题反馈</option>
        <option value="service">服务建议</option>
      </select>
      <textarea name="content" placeholder="请输入反馈内容" />
      <button type="submit" disabled={pending}>{pending ? "提交中" : "提交反馈"}</button>
    </form>
  );
}
