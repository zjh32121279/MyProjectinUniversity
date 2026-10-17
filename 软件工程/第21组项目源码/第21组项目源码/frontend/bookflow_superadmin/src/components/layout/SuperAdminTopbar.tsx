import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppIcon } from "@/components/icons/AppIcon";
import { useLogout } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";
import { useLocation, useNavigate } from "react-router-dom";
import { superAdminApi } from "@/api/superAdmin";
import { formatDateTime } from "@common/utils/format";

export function SuperAdminTopbar() {
  const admin = useAuthStore((state) => state.admin);
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  const [showLogout, setShowLogout] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const isHome = location.pathname === "/super-admin/home" || location.pathname === "/super-admin";
  const overview = useQuery({
    queryKey: ["super-admin", "overview"],
    queryFn: superAdminApi.governanceOverview,
    enabled: isHome,
    staleTime: 30_000,
  });

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setShowLogout(false);
      }
    }
    if (showLogout) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showLogout]);

  return (
    <header className="bf-super-topbar">
      <div className="bf-topbar-context">
        {isHome ? (
          <>
            <h1>BookFlow 实时总览</h1>
            <span>数据更新时间：{formatDateTime(overview.data?.updated_at)}</span>
            <span className="live">实时更新</span>
          </>
        ) : null}
      </div>

      <div className="bf-topbar-actions">
        <button className="relative flex h-11 w-11 items-center justify-center rounded-full text-[#53617e] hover:bg-[#f2f6ff]" onClick={() => navigate("/super-admin/audit-security")} type="button" title="审计安全">
          <span className="sr-only">审计安全</span>
          <AppIcon name="bell" size={25} />
        </button>

        <div className="relative" ref={popoverRef}>
          <button
            className="flex shrink-0 items-center gap-3 rounded-[14px] px-2 py-1.5 text-[#071434] hover:bg-[#f2f6ff]"
            onClick={() => setShowLogout((v) => !v)}
            title={admin?.admin_code ?? "超级管理员"}
            type="button"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-[#e8efff] text-[#0d4fb9]">
              <AppIcon name="user" size={36} />
            </span>
            <span className="hidden min-w-0 text-left leading-tight md:block">
              <span className="block text-[17px] font-black">超级管理员</span>
              <span className="block max-w-[170px] truncate text-[12px] font-bold text-[#6b7690]">{admin?.admin_code}</span>
            </span>
          </button>

          {showLogout && (
            <div className="absolute right-0 top-full mt-2 w-44 rounded-xl border border-[#dfe6f1] bg-white py-1.5 shadow-[0_8px_24px_rgba(8,24,55,0.12)]">
              <button
                className="flex w-full items-center gap-2.5 px-4 py-2.5 text-[14px] font-semibold text-[#e03131] transition-colors hover:bg-[#fef2f2]"
                disabled={logout.isPending}
                onClick={() => { logout.mutate(); setShowLogout(false); }}
                type="button"
              >
                <AppIcon name="close" size={18} />
                {logout.isPending ? "退出中..." : "退出登录"}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
