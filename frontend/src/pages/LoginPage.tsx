import { ArrowRight, CheckCircle2, Eye, EyeOff, Leaf } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useAppConfig } from "../context/ConfigContext";

export function LoginPage() {
  const { user, login } = useAuth();
  const { config } = useAppConfig();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  if (user) return <Navigate to="/chat" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setSubmitting(true);
    try { await login(email, password); navigate("/chat"); }
    catch (err) { setError(err instanceof Error ? err.message : "登入失敗。"); }
    finally { setSubmitting(false); }
  }

  return (
    <div className="auth-page">
      <section className="auth-story">
        <div className="auth-glow one" /><div className="auth-glow two" />
        <div className="auth-brand"><span className="brand-mark">{config.app_icon}</span><span>{config.app_name}</span></div>
        <div className="story-content">
          <div className="eyebrow"><Leaf size={16} /> {config.app_tagline}</div>
          <h1>{config.app_name}</h1>
          <p>{config.app_description}</p>
          <div className="auth-benefits">
            {config.enable_turtle_module && <span><CheckCircle2 size={17} /> {config.profile_label}</span>}
            <span><CheckCircle2 size={17} /> 可自行替換 Markdown 知識庫</span>
            <span><CheckCircle2 size={17} /> NVIDIA NIM 雲端 AI 與清楚引用</span>
          </div>
        </div>
        <div className="shell-pattern" aria-hidden="true"><span /><span /><span /><span /><span /></div>
      </section>
      <section className="auth-form-side">
        <form className="auth-form" onSubmit={submit}>
          <div className="mobile-auth-brand"><span className="brand-mark">{config.app_icon}</span>{config.app_name}</div>
          <span className="form-kicker">歡迎回來</span><h2>登入 {config.app_short_name}</h2><p>繼續查看知識庫與 AI 對話。</p>
          {error && <div className="form-error" role="alert">{error}</div>}
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required autoComplete="email" /></label>
          <label>密碼<div className="password-input"><input type={showPassword ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="輸入密碼" required autoComplete="current-password" /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label="顯示或隱藏密碼">{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
          <button className="primary-button auth-submit" disabled={submitting}>{submitting ? "登入中…" : <>登入 <ArrowRight size={18} /></>}</button>
          <div className="auth-switch">還沒有帳號？ <Link to="/register">建立免費帳號</Link></div>
        </form>
      </section>
    </div>
  );
}
