import { useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, UserRound } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { BookFlowLogo } from "@/components/common/BookFlowLogo";
import { useReaderProfile } from "@/hooks/useReaderProfile";
import { getReaderSession } from "@/services/readerApi";
import { userAuthApi } from "@/services/userAuthApi";

const NAV_ITEMS = [
  { label: "首页", path: "/home" },
  { label: "找书", path: "/search" },
  { label: "我的借阅", path: "/borrows" },
  { label: "我的预约", path: "/reservations" },
  { label: "通知", path: "/notifications" },
  { label: "个人中心", path: "/profile" },
];

export function UserTopNav() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const session = getReaderSession();
  const isReader = Boolean(session);
  const profile = useReaderProfile();
  const name = isReader ? (profile.data?.name || "读者") : "游客浏览";
  const avatar = profile.data?.avatar_url;
  const navItems = isReader ? NAV_ITEMS : NAV_ITEMS.filter((item) => item.path === "/home" || item.path === "/search");

  return (
    <header className="user-topnav">
      <BookFlowLogo compact />
      <nav>
        {navItems.map((item) => (
          <NavLink key={item.path} to={item.path} className={({ isActive }) => (isActive ? "is-active" : "")}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="user-topnav__actions">
        <span
          className="user-profile-mini"
          style={{ cursor: "pointer" }}
          onClick={() => { if (isReader) setOpen(true); else navigate("/login"); }}
          title={isReader ? "退出登录" : "去登录"}
        >
          {avatar ? <img src={avatar} alt="" /> : <UserRound size={21} />}
          <strong>{name}</strong>
          <ChevronDown size={16} />
        </span>
      </div>

      {open &&
        createPortal(
          <div className="logout-overlay" role="dialog" aria-modal="true" aria-label="退出登录">
            <div className="logout-overlay__backdrop" onClick={() => setOpen(false)} />
            <div className="logout-overlay__panel">
              <h3>退出登录</h3>
              <p>确定要退出当前账号吗？退出后需要重新登录才能使用借阅、预约等功能。</p>
              <div className="logout-overlay__actions">
                <button type="button" className="logout-overlay__cancel" onClick={() => setOpen(false)}>取消</button>
                <button type="button" className="logout-overlay__confirm" onClick={() => { userAuthApi.logout().finally(() => { navigate("/login", { replace: true }); }); }}>确认退出</button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </header>
  );
}
