import { useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AppIcon } from "@/components/icons/AppIcon";
import { SearchInput } from "@/components/ui/SearchInput";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useLogout } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";

type TopbarProps = {
  pageActions?: ReactNode;
  showSearch?: boolean;
  searchPlaceholder?: string;
};

function routeChrome(pathname: string): { showSearch: boolean; searchPlaceholder: string; actions?: ReactNode } {
  if (pathname.includes("/admin/ai")) {
    return { showSearch: false, searchPlaceholder: "" };
  }
  if (pathname.includes("/admin/borrowing")) {
    return { showSearch: false, searchPlaceholder: "" };
  }
  if (pathname.includes("/admin/readers")) {
    return { showSearch: false, searchPlaceholder: "" };
  }
  if (pathname.includes("/admin/data")) {
    return { showSearch: false, searchPlaceholder: "" };
  }
  if (pathname.includes("/admin/notifications")) {
    return { showSearch: false, searchPlaceholder: "" };
  }
  if (pathname.includes("/admin/settings")) {
    return { showSearch: false, searchPlaceholder: "" };
  }
  if (pathname.includes("/admin/tasks")) {
    return { showSearch: false, searchPlaceholder: "" };
  }
  return { showSearch: false, searchPlaceholder: "" };
}

export function Topbar({ pageActions, showSearch, searchPlaceholder }: TopbarProps) {
  const admin = useAuthStore((state) => state.admin);
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);
  const chrome = routeChrome(location.pathname);
  const resolvedShowSearch = showSearch ?? chrome.showSearch;
  const resolvedPlaceholder = searchPlaceholder ?? chrome.searchPlaceholder;
  const resolvedActions = pageActions ?? chrome.actions;

  return (
    <header className="bf-topbar sticky top-0 z-10 flex h-[var(--bf-topbar-height)] min-w-0 items-center justify-between gap-4 border-0 bg-[var(--bf-bg)] px-5 shadow-none md:px-8 lg:px-10">
      <div className="min-w-0 flex-1">
        {resolvedShowSearch ? <SearchInput className="w-full max-w-[500px]" placeholder={resolvedPlaceholder} /> : null}
      </div>
      <div className="flex shrink-0 items-center gap-3 lg:gap-4">
        {resolvedActions ? <div className="flex shrink-0 items-center gap-2 lg:gap-3">{resolvedActions}</div> : null}
        <button className="relative flex h-11 w-11 items-center justify-center rounded-full text-[#15213e] hover:bg-[#f7faff]" type="button" title="通知中心" onClick={() => navigate("/admin/notifications")}>
          <AppIcon name="bell" size={24} />
        </button>
        <button className="flex shrink-0 items-center gap-3 rounded-2xl px-2 py-1.5 hover:bg-[#f7faff]" type="button" title="退出登录" onClick={() => setLogoutConfirmOpen(true)}>
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-[#5867ff] to-[#7c3aed] text-white shadow-[0_12px_24px_rgba(79,70,229,0.18)]">
            <AppIcon name="user" size={34} className="text-white" />
          </div>
          <div className="hidden text-left leading-tight xl:block">
            <div className="text-[16px] font-black text-[#101a35]">{admin?.name || (admin?.is_super_admin ? "超级管理员" : "普通管理员")}</div>
          </div>
          <AppIcon name="down" size={18} className="hidden text-[#64748b] xl:block" />
        </button>
      </div>

      <ConfirmDialog
        open={logoutConfirmOpen}
        onOpenChange={setLogoutConfirmOpen}
        title="退出登录"
        description="确定要退出当前账号吗？"
        onConfirm={() => logout.mutate()}
      />
    </header>
  );
}
