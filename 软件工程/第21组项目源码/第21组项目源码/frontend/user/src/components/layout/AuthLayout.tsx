import type { ReactNode } from "react";
import { Landmark } from "lucide-react";
import { BookFlowLogo } from "@/components/common/BookFlowLogo";

type AuthLayoutProps = {
  children?: ReactNode;
};

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <main className="auth-page">
      <div className="app-background app-background--auth" />

      <section className="auth-hero" aria-label="BookFlow">
        <BookFlowLogo />
        <div className="auth-hero__copy">
          <h1>让阅读，流动起来</h1>
          <p>连接你与知识的每一次相遇，</p>
          <p>在书香中，发现更好的自己。</p>
        </div>
      </section>

      <section className="auth-card glass-panel">{children}</section>

      <footer className="auth-footer">
        <p>
          <Landmark size={18} />
          <span>BookFlow · 让阅读更简单，让知识更有温度</span>
        </p>
        <small>本服务由各参与公共图书馆联合提供</small>
      </footer>
    </main>
  );
}
