import { BookOpenIcon } from "@heroicons/react/24/solid";
import { NavLink } from "react-router-dom";
import { AppIcon, type AppIconName } from "@/components/icons/AppIcon";
import { cn } from "@common/utils/cn";
import sidebarArt from "@/assets/super-admin/sidebar-art.png";

const navItems: Array<{ to: string; label: string; icon: AppIconName }> = [
  { to: "/super-admin/home", label: "治理首页", icon: "home" },
  { to: "/super-admin/admins", label: "管理员管理", icon: "readers" },
  { to: "/super-admin/ai-rules", label: "AI 与规则", icon: "ai" },
  { to: "/super-admin/audit-security", label: "审计安全", icon: "lock" },
];

type SuperAdminSidebarProps = {
  collapsed: boolean;
  onToggle: () => void;
};

export function SuperAdminSidebar({ collapsed, onToggle }: SuperAdminSidebarProps) {
  return (
    <aside
      className="bf-super-sidebar"
      data-testid="super-admin-sidebar"
      style={{ width: collapsed ? "var(--bf-super-sidebar-collapsed-width)" : "var(--bf-super-sidebar-width)" }}
    >
      <div className={cn("flex h-[var(--bf-super-topbar-height)] items-center gap-3 px-7 text-white", collapsed && "justify-center px-0")}>
        <BookOpenIcon className="h-9 w-9 shrink-0 drop-shadow-[0_8px_18px_rgba(47,128,255,0.38)]" />
        {!collapsed ? <span className="whitespace-nowrap text-[25px] font-black leading-none">BookFlow</span> : null}
      </div>

      <nav className={cn("flex-1 space-y-4 pt-7", collapsed ? "px-3" : "px-4")}>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "grid h-[58px] items-center gap-4 rounded-[9px] px-5 text-[17px] font-extrabold transition",
                collapsed ? "grid-cols-1 justify-items-center px-0" : "grid-cols-[24px_minmax(0,1fr)]",
                isActive ? "bg-[#1f6df2] shadow-[0_14px_28px_rgba(10,91,225,0.34)]" : "hover:bg-white/8",
              )
            }
            style={({ isActive }) => ({ color: isActive ? "#ffffff" : "rgba(219, 234, 254, 0.78)" })}
            title={collapsed ? item.label : undefined}
          >
            <AppIcon name={item.icon} size={25} />
            {!collapsed ? <span className="min-w-0 truncate whitespace-nowrap">{item.label}</span> : null}
          </NavLink>
        ))}
      </nav>

      {!collapsed ? (
        <div className="mx-4 mb-4 mt-auto h-[266px] overflow-hidden rounded-[8px]" aria-hidden="true">
          <img src={sidebarArt} alt="" className="h-full w-full object-cover object-bottom opacity-[0.78]" />
        </div>
      ) : (
        <div className="flex-1" />
      )}

      <button
        className={cn("mb-7 flex h-12 items-center gap-3 text-[16px] font-extrabold text-white/82", collapsed ? "mx-auto justify-center" : "ml-7")}
        onClick={onToggle}
        type="button"
        title={collapsed ? "展开菜单" : "收起菜单"}
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 ring-1 ring-white/12">
          <AppIcon name={collapsed ? "right" : "left"} size={18} />
        </span>
        {!collapsed ? "收起菜单" : null}
      </button>
    </aside>
  );
}
