import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { useDashboard } from "@/hooks/useDashboard";
import { getNumber } from "@/utils/format";
import { getViewportInfo } from "@/utils/viewport";
import { cn } from "@/utils/cn";

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const dashboard = useDashboard();
  const taskCount = getNumber(dashboard.data, "pending_task_count", 0);
  useEffect(() => {
    if (import.meta.env.DEV) {
      console.info("[BookFlow viewport]", getViewportInfo());
    }
  }, []);

  return (
    <div className="bf-app-shell min-h-screen min-w-0 bg-[var(--bf-bg)]">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} taskCount={taskCount} />
      <div
        className="min-w-0 transition-all duration-200"
        style={{ marginLeft: collapsed ? "var(--bf-sidebar-collapsed-width)" : "var(--bf-sidebar-width)" }}
      >
        <Topbar />
        <main
          className={cn(
            "bf-main-scroll min-w-0 overflow-x-hidden overflow-y-auto px-5 pt-4 pb-8 md:px-6 lg:px-7 xl:px-8",
            "min-h-[calc(100vh-var(--bf-topbar-height))]",
          )}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
