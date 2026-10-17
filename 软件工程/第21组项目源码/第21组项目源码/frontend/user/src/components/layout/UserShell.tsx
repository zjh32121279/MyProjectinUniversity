import { Outlet, useLocation } from "react-router-dom";
import { UserTopNav } from "@/components/layout/UserTopNav";
import { DraggableBookFlowAI } from "@/components/ai/DraggableBookFlowAI";

export function UserShell() {
  const location = useLocation();
  const backgroundClass = location.pathname === "/home" ? "user-background--home" : "user-background--content";

  return (
    <div className="user-shell">
      <div className={`app-background user-background ${backgroundClass}`} />
      <UserTopNav />
      <Outlet />
      <DraggableBookFlowAI />
    </div>
  );
}
