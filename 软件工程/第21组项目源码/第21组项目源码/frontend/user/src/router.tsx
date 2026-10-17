import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import App from "@/App";
import { UserShell } from "@/components/layout/UserShell";
import { RequireReader } from "@/components/layout/RequireReader";

const LoginPage = lazy(() => import("@/pages/auth/LoginPage").then((module) => ({ default: module.LoginPage })));
const RegisterPage = lazy(() => import("@/pages/auth/RegisterPage").then((module) => ({ default: module.RegisterPage })));
const ForgotPasswordPage = lazy(() => import("@/pages/auth/ForgotPasswordPage").then((module) => ({ default: module.ForgotPasswordPage })));
const HomePage = lazy(() => import("@/pages/HomePage").then((module) => ({ default: module.HomePage })));
const SearchBooksPage = lazy(() => import("@/pages/SearchBooksPage").then((module) => ({ default: module.SearchBooksPage })));
const BorrowPage = lazy(() => import("@/pages/BorrowPage").then((module) => ({ default: module.BorrowPage })));
const ReservationPage = lazy(() => import("@/pages/ReservationPage").then((module) => ({ default: module.ReservationPage })));
const NotificationPage = lazy(() => import("@/pages/NotificationPage").then((module) => ({ default: module.NotificationPage })));
const ProfilePage = lazy(() => import("@/pages/ProfilePage").then((module) => ({ default: module.ProfilePage })));

function PageBoundary({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<div className="route-loading" role="status">加载中...</div>}>
      {children}
    </Suspense>
  );
}

function page(element: ReactNode) {
  return <PageBoundary>{element}</PageBoundary>;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/login" replace /> },
      { path: "login", element: page(<LoginPage />) },
      { path: "register", element: page(<RegisterPage />) },
      { path: "forgot-password", element: page(<ForgotPasswordPage />) },
      {
        element: <UserShell />,
        children: [
          { path: "home", element: page(<HomePage />) },
          { path: "search", element: page(<SearchBooksPage />) },
          { path: "borrows", element: page(<RequireReader><BorrowPage /></RequireReader>) },
          { path: "reservations", element: page(<RequireReader><ReservationPage /></RequireReader>) },
          { path: "notifications", element: page(<RequireReader><NotificationPage /></RequireReader>) },
          { path: "profile", element: page(<RequireReader><ProfilePage /></RequireReader>) },
        ],
      },
    ],
  },
]);
