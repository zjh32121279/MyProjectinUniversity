import { useState } from "react";
import { Outlet } from "react-router-dom";
import { SuperAdminSidebar } from "@/components/layout/SuperAdminSidebar";
import { SuperAdminTopbar } from "@/components/layout/SuperAdminTopbar";

export function SuperAdminShell() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="bf-super-shell">
      <SuperAdminSidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} />
      <div
        className="bf-super-content"
        style={{ marginLeft: collapsed ? "var(--bf-super-sidebar-collapsed-width)" : "var(--bf-super-sidebar-width)" }}
      >
        <SuperAdminTopbar />
        <main className="bf-super-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
