import { useEffect } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { SuperAdminShell } from "@/components/layout/SuperAdminShell";
import { SkeletonBlock } from "@/components/ui/States";
import { useCurrentAdmin } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";
import { LoginPage } from "@/pages/LoginPage";
import { GovernanceHomePage } from "@/pages/GovernanceHomePage";
import { AdminManagementPage } from "@/pages/AdminManagementPage";
import { AiRulesPage } from "@/pages/AiRulesPage";
import { AuditSecurityPage } from "@/pages/AuditSecurityPage";

function RequireAuth() {
  const token = useAuthStore((state) => state.token);
  const setAdmin = useAuthStore((state) => state.setAdmin);
  const clear = useAuthStore((state) => state.clear);
  const current = useCurrentAdmin(Boolean(token));

  useEffect(() => {
    if (current.data) setAdmin(current.data);
  }, [current.data, setAdmin]);

  useEffect(() => {
    if (current.isError) clear();
  }, [current.isError, clear]);

  if (!token) return <Navigate to="/login" replace />;
  if (current.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bf-super-bg)]">
        <SkeletonBlock className="h-24 w-96" />
      </div>
    );
  }
  if (current.isError) return <Navigate to="/login" replace />;
  if (!current.data?.is_super_admin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bf-super-bg)] p-8">
        <div className="max-w-md rounded-[8px] border border-[#ffd5d5] bg-white p-8 text-center shadow-sm">
          <div className="text-[20px] font-black text-[#ef4444]">无权访问超级管理员端</div>
          <div className="mt-3 text-sm font-semibold leading-6 text-[#64718d]">请使用超级管理员账号登录。</div>
          <a className="mt-6 inline-flex rounded-[8px] bg-[#1769f7] px-5 py-2.5 text-sm font-black text-white" href="/login">
            返回登录
          </a>
        </div>
      </div>
    );
  }
  return <Outlet />;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/super-admin" element={<SuperAdminShell />}>
            <Route index element={<Navigate to="/super-admin/home" replace />} />
            <Route path="home" element={<GovernanceHomePage />} />
            <Route path="admins" element={<AdminManagementPage />} />
            <Route path="ai-rules" element={<AiRulesPage />} />
            <Route path="audit-security" element={<AuditSecurityPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/super-admin/home" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
