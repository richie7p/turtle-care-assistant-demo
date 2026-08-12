import { Bot, Check, KeyRound, Palette, Save, SlidersHorizontal } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useAppConfig } from "../context/ConfigContext";
import { api } from "../lib/api";
import type { Turtle, UserSettings } from "../types";

export function SettingsPage() {
  const { user } = useAuth(); const [settings, setSettings] = useState<UserSettings>({ theme: "light", response_style: "balanced" });
  const { config } = useAppConfig();
  const [turtles, setTurtles] = useState<Turtle[]>([]); const [saved, setSaved] = useState(false); const [error, setError] = useState("");
  useEffect(() => { Promise.all([api<UserSettings>("/settings"), config.enable_turtle_module ? api<Turtle[]>("/turtles") : Promise.resolve([])]).then(([a, b]) => { setSettings(a); setTurtles(b); }).catch((err) => setError(err.message)); }, [config.enable_turtle_module]);
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); try { setSettings(await api<UserSettings>("/settings", { method: "PATCH", body: JSON.stringify(settings) })); setSaved(true); setTimeout(() => setSaved(false), 2200); } catch (err) { setError(err instanceof Error ? err.message : "儲存失敗。"); } }
  return <div className="page-shell settings-page"><header className="page-header"><div><span className="header-kicker">Preferences</span><h1>設定</h1><p>調整回答詳細度與介面偏好。</p></div></header>{error && <div className="form-error">{error}</div>}
    <form onSubmit={submit} className="settings-layout"><section className="settings-card"><div className="settings-section-title"><div><SlidersHorizontal size={20} /></div><span><h2>AI 回答偏好</h2><p>套用到之後的新回答</p></span></div>{config.enable_turtle_module && <label>預設詢問龜龜<select value={settings.default_turtle_id ?? ""} onChange={(e) => setSettings({ ...settings, default_turtle_id: e.target.value || undefined })}><option value="">每次自行選擇</option>{turtles.map((turtle) => <option value={turtle.id} key={turtle.id}>{turtle.name} · {turtle.species}</option>)}</select></label>}<label>回答詳細度<div className="segment-control">{([['concise','精簡'],['balanced','適中'],['detailed','詳細']] as const).map(([value, label]) => <button type="button" key={value} className={settings.response_style === value ? "selected" : ""} onClick={() => setSettings({ ...settings, response_style: value })}>{label}</button>)}</div></label></section>
      <section className="settings-card"><div className="settings-section-title"><div><Palette size={20} /></div><span><h2>介面外觀</h2><p>第一版提供明亮自然主題</p></span></div><div className="theme-preview selected"><div className="theme-swatch"><i /><i /><i /></div><span><strong>自然明亮</strong><small>暖白、苔綠與湖水藍</small></span><Check size={18} /></div></section>
      <section className="settings-card account-card"><div className="settings-section-title"><div><KeyRound size={20} /></div><span><h2>帳號與模型</h2><p>敏感資訊只保存在伺服器</p></span></div><div className="account-row"><span>名稱</span><strong>{user?.display_name}</strong></div><div className="account-row"><span>Email</span><strong>{user?.email}</strong></div><div className="model-chip"><Bot size={17} /><span><small>AI Provider</small><strong>{config.ai_provider} · {config.ai_configured ? "已設定" : "尚未設定 API Key"}</strong></span></div></section>
      <div className="settings-save"><button className="primary-button"><Save size={18} />{saved ? "已儲存" : "儲存設定"}</button></div>
    </form>
  </div>;
}
