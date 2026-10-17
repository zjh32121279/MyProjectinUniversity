import { useEffect } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { useCurrentAdmin } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";
import { startAutoRefresh } from "@/api/auth";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { LoginPage } from "@/pages/LoginPage";
import { AIWorkbenchPage } from "@/pages/admin/AIWorkbenchPage";
import { BorrowingHomePage } from "@/pages/admin/borrowing/BorrowingHomePage";
import { BorrowBookPage } from "@/pages/admin/borrowing/BorrowBookPage";
import { ReturnBookPage } from "@/pages/admin/borrowing/ReturnBookPage";
import { RenewBookPage } from "@/pages/admin/borrowing/RenewBookPage";
import { ReservationPage } from "@/pages/admin/borrowing/ReservationPage";
import { CatalogPage } from "@/pages/admin/CatalogPage";
import { DataCenterPage } from "@/pages/admin/DataCenterPage";
import { HomePage } from "@/pages/admin/HomePage";
import { NotificationsPage } from "@/pages/admin/NotificationsPage";
import { ReadersPage } from "@/pages/admin/ReadersPage";
import { SettingsPage } from "@/pages/admin/SettingsPage";
import { TasksPage } from "@/pages/admin/TasksPage";

function RequireAuth() {
  const token = useAuthStore((state) => state.token);
  const setAdmin = useAuthStore((state) => state.setAdmin);
  const clear = useAuthStore((state) => state.clear);
  const current = useCurrentAdmin(Boolean(token));

  useEffect(() => { startAutoRefresh(); }, []);

  useEffect(() => {
    if (current.data) setAdmin(current.data);
  }, [current.data, setAdmin]);

  useEffect(() => {
    if (current.isError) clear();
  }, [current.isError, clear]);

  if (!token) return <Navigate to="/login" replace />;
  if (current.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bf-bg)]">
        <SkeletonBlock className="h-24 w-96" />
      </div>
    );
  }
  if (current.isError) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/admin" element={<AppShell />}>
            <Route index element={<Navigate to="/admin/home" replace />} />
            <Route path="home" element={<HomePage />} />
            <Route path="ai" element={<AIWorkbenchPage />} />
            <Route path="borrowing" element={<BorrowingHomePage />} />
            <Route path="borrowing/borrow" element={<BorrowBookPage />} />
            <Route path="borrowing/return" element={<ReturnBookPage />} />
            <Route path="borrowing/renew" element={<RenewBookPage />} />
            <Route path="borrowing/reservation" element={<ReservationPage />} />
            <Route path="tasks" element={<TasksPage />} />
            <Route path="data" element={<DataCenterPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="readers" element={<ReadersPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="catalog" element={<CatalogPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/admin/home" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
