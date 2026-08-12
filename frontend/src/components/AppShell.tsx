import { BookOpen, LogOut, Menu, MessageCircle, Settings, ShieldCheck, Turtle, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useAppConfig } from "../context/ConfigContext";

export function AppShell() {
  const { user, logout } = useAuth();
  const { config } = useAppConfig();
  const [open, setOpen] = useState(false);
  const navItems = [
    { to: "/chat", label: "AI 對話", icon: MessageCircle, enabled: true },
    { to: "/turtles", label: config.profile_label, icon: Turtle, enabled: config.enable_turtle_module },
    { to: "/knowledge", label: config.knowledge_label, icon: BookOpen, enabled: true },
    { to: "/settings", label: "設定", icon: Settings, enabled: true },
  ].filter((item) => item.enabled);
  return (
    <div className="app-shell">
      <button className="mobile-nav-button" onClick={() => setOpen(true)} aria-label="開啟選單"><Menu size={22} /></button>
      {open && <button className="nav-overlay" onClick={() => setOpen(false)} aria-label="關閉選單" />}
      <aside className={`main-nav ${open ? "open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark" aria-hidden="true">{config.app_icon}</div>
          <div><strong>{config.app_short_name}</strong><span>{config.assistant_name}</span></div>
          <button className="icon-button nav-close" onClick={() => setOpen(false)} aria-label="關閉選單"><X size={20} /></button>
        </div>
        <nav>
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? "active" : ""}>
              <Icon size={19} /><span>{label}</span>
            </NavLink>
          ))}
          {user?.role === "admin" && (
            <NavLink to="/admin" onClick={() => setOpen(false)} className={({ isActive }) => isActive ? "active" : ""}>
              <ShieldCheck size={19} /><span>系統管理</span>
            </NavLink>
          )}
        </nav>
        <div className="nav-spacer" />
        <div className="user-card">
          <div className="avatar">{user?.display_name.slice(0, 1).toUpperCase()}</div>
          <div className="user-meta"><strong>{user?.display_name}</strong><span>{user?.email}</span></div>
          <button className="icon-button" onClick={() => void logout()} title="登出" aria-label="登出"><LogOut size={18} /></button>
        </div>
      </aside>
      <main className="app-content"><Outlet /></main>
    </div>
  );
}
