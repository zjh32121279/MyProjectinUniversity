import { NavLink } from "react-router-dom";
import { AppIcon, type AppIconName } from "@/components/icons/AppIcon";
import { BookFlowMark } from "@/components/layout/BookFlowMark";
import { cn } from "@/utils/cn";

const navItems: Array<{ to: string; label: string; icon: AppIconName; badge?: string }> = [
  { to: "/admin/home", label: "首页", icon: "home" },
  { to: "/admin/ai", label: "AI 工作台", icon: "ai" },
  { to: "/admin/tasks", label: "任务中心", icon: "tasks", badge: "tasks" },
  { to: "/admin/catalog", label: "馆藏管理", icon: "catalog" },
  { to: "/admin/borrowing", label: "借阅与预约", icon: "borrowing" },
  { to: "/admin/readers", label: "读者管理", icon: "readers" },
  { to: "/admin/notifications", label: "通知中心", icon: "notifications" },
  { to: "/admin/data", label: "数据中心", icon: "data" },
  { to: "/admin/settings", label: "系统设置", icon: "settings" },
];

type SidebarProps = {
  collapsed: boolean;
  onToggle: () => void;
  taskCount?: number;
};

export function Sidebar({ collapsed, onToggle, taskCount }: SidebarProps) {
  return (
    <aside
      data-testid="app-sidebar"
      className={cn(
        "bf-sidebar fixed left-0 top-0 z-20 flex h-screen flex-shrink-0 flex-col overflow-hidden border-0 bg-[var(--bf-bg)] shadow-none transition-all duration-200",
        collapsed ? "w-[var(--bf-sidebar-collapsed-width)] min-w-[var(--bf-sidebar-collapsed-width)] max-w-[var(--bf-sidebar-collapsed-width)]" : "w-[var(--bf-sidebar-width)] min-w-[var(--bf-sidebar-width)] max-w-[var(--bf-sidebar-width)]",
      )}
    >
      <div className="bf-brand-header flex h-[var(--bf-topbar-height)] min-h-[var(--bf-topbar-height)] items-center border-0 bg-transparent px-8 shadow-none">
        <BookFlowMark compact={collapsed} />
      </div>
      <nav className="flex-1 space-y-2.5 px-5 pt-5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "group grid h-[54px] grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-3 rounded-[9px] px-4 text-[17px] font-bold text-[#33415f] transition",
                isActive ? "bg-[#f0ecff] text-[#4f46e5] shadow-[0_10px_24px_rgba(91,75,242,0.08)]" : "hover:bg-[#f7faff]",
                collapsed && "flex justify-center px-0",
              )
            }
          >
            <AppIcon name={item.icon} size={22} />
            {!collapsed ? <span className="min-w-0 truncate whitespace-nowrap leading-5">{item.label}</span> : null}
            {!collapsed && item.badge === "tasks" && taskCount ? (
              <span className="flex h-7 min-w-7 items-center justify-center rounded-full bg-[#ebe7ff] px-2 text-sm font-black text-[#5b4bf2]">{taskCount}</span>
            ) : null}
          </NavLink>
        ))}
      </nav>
      <button className="mb-8 ml-7 flex h-11 items-center gap-3 whitespace-nowrap text-base font-bold text-[#1f2a44]" onClick={onToggle} type="button">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#f5f8ff]">
          <AppIcon name={collapsed ? "right" : "left"} size={19} />
        </span>
        {!collapsed ? "收起菜单" : null}
      </button>
    </aside>
  );
}
