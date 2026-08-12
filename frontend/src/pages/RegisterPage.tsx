import { ArrowRight, Eye, EyeOff, Leaf } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useAppConfig } from "../context/ConfigContext";

export function RegisterPage() {
  const { user, register } = useAuth();
  const { config } = useAppConfig();
  const navigate = useNavigate();
  const [form, setForm] = useState({ displayName: "", email: "", password: "" });
  const [show, setShow] = useState(false); const [error, setError] = useState(""); const [submitting, setSubmitting] = useState(false);
  if (user) return <Navigate to="/chat" replace />;
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setSubmitting(true);
    try { await register(form.email, form.displayName, form.password); navigate("/chat"); }
    catch (err) { setError(err instanceof Error ? err.message : "註冊失敗。"); }
    finally { setSubmitting(false); }
  }
  return (
    <div className="auth-page">
      <section className="auth-story register-story">
        <div className="auth-glow one" /><div className="auth-glow two" />
        <div className="auth-brand"><span className="brand-mark">{config.app_icon}</span><span>{config.app_name}</span></div>
        <div className="story-content"><div className="eyebrow"><Leaf size={16} /> {config.app_tagline}</div><h1>建立你的<br />專屬知識助理。</h1><p>{config.app_description}</p></div>
        <div className="shell-pattern" aria-hidden="true"><span /><span /><span /><span /><span /></div>
      </section>
      <section className="auth-form-side"><form className="auth-form" onSubmit={submit}>
        <div className="mobile-auth-brand"><span className="brand-mark">{config.app_icon}</span>{config.app_name}</div>
        <span className="form-kicker">開始使用</span><h2>建立你的帳號</h2><p>你的對話、圖片與個人資料只屬於你。</p>
        {error && <div className="form-error" role="alert">{error}</div>}
        <label>顯示名稱<input value={form.displayName} onChange={(e) => setForm({ ...form, displayName: e.target.value })} placeholder="例如：知識庫使用者" required maxLength={80} /></label>
        <label>Email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@example.com" required autoComplete="email" /></label>
        <label>密碼<div className="password-input"><input type={show ? "text" : "password"} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="至少 8 個字元" minLength={8} required autoComplete="new-password" /><button type="button" onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
        <button className="primary-button auth-submit" disabled={submitting}>{submitting ? "建立中…" : <>建立帳號 <ArrowRight size={18} /></>}</button>
        <div className="auth-switch">已經有帳號？ <Link to="/login">直接登入</Link></div>
      </form></section>
    </div>
  );
}
