import { LockClosedIcon, UserCircleIcon } from "@heroicons/react/24/outline";
import { BookOpenIcon } from "@heroicons/react/24/solid";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import backgroundUrl from "../assets/login/background.png";

type SharedLoginViewProps = {
  token: string | null;
  redirectTo: string;
  isPending: boolean;
  errorMessage?: string;
  onSubmit: (account: string, password: string) => void;
};

function BookFlowMark() {
  return (
    <div className="flex flex-col items-center">
      <span className="relative flex h-24 w-24 items-center justify-center text-[#2563eb]">
        <BookOpenIcon className="h-20 w-20 drop-shadow-[0_12px_24px_rgba(37,99,235,0.18)]" />
      </span>
      <span className="mt-3 bg-gradient-to-r from-[#0f61ff] to-[#7c3aed] bg-clip-text text-[48px] font-black leading-none text-transparent">BookFlow</span>
    </div>
  );
}

export function SharedLoginView({ token, redirectTo, isPending, errorMessage, onSubmit }: SharedLoginViewProps) {
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");

  if (token) return <Navigate to={redirectTo} replace />;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(account.trim(), password);
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#dbeafe]">
      <img src={backgroundUrl} alt="" className="absolute inset-0 h-full w-full object-cover" />
      <div className="absolute inset-0 bg-white/10" />
      <section className="relative z-10 flex min-h-screen items-center justify-center px-4 py-8 sm:px-8 lg:justify-end lg:px-[7.5vw]">
        <form onSubmit={handleSubmit} className="min-h-[min(620px,calc(100vh-64px))] w-full max-w-[600px] rounded-[30px] border border-white/80 bg-white/90 px-6 py-8 shadow-[0_32px_90px_rgba(54,80,150,0.2)] backdrop-blur-xl sm:px-10 sm:py-12 xl:px-[58px] xl:py-[60px]">
          <div className="flex flex-col items-center">
            <BookFlowMark />
            <div className="mt-6 flex items-center gap-4 text-[19px] font-bold text-[#9aa6bd]">
              <span className="h-px w-10 bg-[#d8dcff]" />
              管理端登录
              <span className="h-px w-10 bg-[#d8dcff]" />
            </div>
          </div>

          <label className="mt-10 flex h-[64px] items-center gap-4 rounded-[13px] border border-[#d8deeb] bg-white/82 px-5 text-[#9aa6bd] transition focus-within:border-[#6b8cff] focus-within:shadow-[0_0_0_4px_rgba(37,99,235,0.08)] sm:mt-12 sm:px-7">
            <UserCircleIcon className="h-[23px] w-[23px] shrink-0" />
            <input
              value={account}
              onChange={(event) => setAccount(event.target.value)}
              className="min-w-0 flex-1 border-0 bg-transparent text-base font-semibold text-[#111827] outline-none placeholder:text-[#a8b2c4]"
              placeholder="账号"
              autoComplete="username"
              required
            />
          </label>

          <label className="mt-6 flex h-[64px] items-center gap-4 rounded-[13px] border border-[#d8deeb] bg-white/82 px-5 text-[#9aa6bd] transition focus-within:border-[#6b8cff] focus-within:shadow-[0_0_0_4px_rgba(37,99,235,0.08)] sm:px-7">
            <LockClosedIcon className="h-[23px] w-[23px] shrink-0" />
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="min-w-0 flex-1 border-0 bg-transparent text-base font-semibold text-[#111827] outline-none placeholder:text-[#a8b2c4]"
              placeholder="密码"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>

          {errorMessage ? <div className="mt-4 rounded-xl bg-[#fef2f2] px-4 py-3 text-sm font-semibold text-[#ef4444]">{errorMessage}</div> : null}

          <button
            type="submit"
            className="mt-10 inline-flex h-[64px] w-full items-center justify-center rounded-[10px] bg-gradient-to-r from-[#3b82f6] to-[#7c3aed] text-xl font-semibold text-white shadow-[0_20px_38px_rgba(79,70,229,0.25)] transition hover:opacity-95 disabled:opacity-50"
            disabled={isPending}
          >
            {isPending ? "登录中..." : "登录"}
          </button>
        </form>
      </section>
    </main>
  );
}
