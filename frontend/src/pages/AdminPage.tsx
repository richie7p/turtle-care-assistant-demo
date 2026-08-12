import {
  Activity,
  Bot,
  BookOpenCheck,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Database,
  History,
  MessageSquare,
  RefreshCw,
  Search,
  ServerCog,
  ShieldCheck,
  Turtle,
  UserCheck,
  UserCog,
  UserX,
  Users,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useAppConfig } from "../context/ConfigContext";
import { api } from "../lib/api";
import type {
  AdminAuditList,
  AdminKnowledgeStatus,
  AdminProviderHealth,
  AdminStats,
  AdminSystemInfo,
  AdminUsageList,
  AdminUser,
  AdminUserList,
} from "../types";

type AdminTab = "overview" | "users" | "usage" | "knowledge" | "system";

const featureLabels: Record<string, string> = {
  chat: "文字對話",
  vision: "圖片分析",
  rag: "知識檢索",
  title: "對話標題",
  summary: "摘要",
};

const tabItems: Array<{ id: AdminTab; label: string; icon: typeof Activity }> = [
  { id: "overview", label: "營運總覽", icon: Activity },
  { id: "users", label: "使用者", icon: Users },
  { id: "usage", label: "AI 紀錄", icon: Zap },
  { id: "knowledge", label: "知識庫", icon: BookOpenCheck },
  { id: "system", label: "系統與稽核", icon: ServerCog },
];

function formatDate(value?: string) {
  return value ? new Date(value).toLocaleString("zh-TW") : "尚無資料";
}

function statusLabel(status: string) {
  return status === "success" ? "成功" : status === "error" ? "錯誤" : status;
}

export function AdminPage() {
  const { user } = useAuth();
  const { config } = useAppConfig();
  const [tab, setTab] = useState<AdminTab>("overview");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserList | null>(null);
  const [usage, setUsage] = useState<AdminUsageList | null>(null);
  const [knowledge, setKnowledge] = useState<AdminKnowledgeStatus | null>(null);
  const [audits, setAudits] = useState<AdminAuditList | null>(null);
  const [system, setSystem] = useState<AdminSystemInfo | null>(null);
  const [providerHealth, setProviderHealth] = useState<AdminProviderHealth | null>(null);
  const [search, setSearch] = useState("");
  const [userPage, setUserPage] = useState(1);
  const [usagePage, setUsagePage] = useState(1);
  const [usageStatus, setUsageStatus] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadStats() {
    setStats(await api<AdminStats>("/admin/stats"));
  }

  async function loadUsers(page = userPage, query = search) {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (query.trim()) params.set("q", query.trim());
    setUsers(await api<AdminUserList>(`/admin/users?${params}`));
  }

  async function loadUsage(page = usagePage, status = usageStatus) {
    const params = new URLSearchParams({ page: String(page), page_size: "30" });
    if (status) params.set("status", status);
    setUsage(await api<AdminUsageList>(`/admin/usage?${params}`));
  }

  async function loadKnowledge() {
    setKnowledge(await api<AdminKnowledgeStatus>("/admin/knowledge"));
  }

  async function loadSystem() {
    const [systemData, auditData] = await Promise.all([
      api<AdminSystemInfo>("/admin/system"),
      api<AdminAuditList>("/admin/audit?limit=50"),
    ]);
    setSystem(systemData);
    setAudits(auditData);
  }

  async function refreshAll() {
    setBusy("refresh"); setError("");
    try {
      await Promise.all([loadStats(), loadUsers(), loadUsage(), loadKnowledge(), loadSystem()]);
      setNotice("管理資料已更新。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法更新管理資料。");
    } finally {
      setBusy("");
    }
  }

  useEffect(() => {
    void refreshAll();
  }, []);

  async function updateUser(target: AdminUser, patch: { role?: "user" | "admin"; is_active?: boolean }) {
    const action = patch.is_active === false
      ? `停用 ${target.email}`
      : patch.role === "admin"
        ? `將 ${target.email} 設為管理員`
        : patch.role === "user"
          ? `將 ${target.email} 改為一般使用者`
          : `啟用 ${target.email}`;
    if (!window.confirm(`確定要${action}嗎？`)) return;
    setBusy(`user-${target.id}`); setError("");
    try {
      await api(`/admin/users/${target.id}`, { method: "PATCH", body: JSON.stringify(patch) });
      await Promise.all([loadUsers(), loadStats(), loadSystem()]);
      setNotice(`${action}完成。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "使用者更新失敗。");
    } finally {
      setBusy("");
    }
  }

  async function checkProvider() {
    setBusy("provider"); setError("");
    try {
      const result = await api<AdminProviderHealth>("/admin/provider/check", { method: "POST" });
      setProviderHealth(result);
      setNotice(result.message);
      await loadSystem();
    } catch (err) {
      setError(err instanceof Error ? err.message : "NVIDIA 連線檢查失敗。");
    } finally {
      setBusy("");
    }
  }

  async function syncKnowledge() {
    if (!window.confirm("確定要掃描 Markdown 並同步缺少或過期的知識向量嗎？")) return;
    setBusy("knowledge"); setError("");
    try {
      const result = await api<{ updated_documents: number; embedded_chunks: number; message: string }>(
        "/admin/knowledge/sync",
        { method: "POST" },
      );
      await Promise.all([loadKnowledge(), loadStats(), loadSystem()]);
      setNotice(`${result.message} 更新 ${result.updated_documents} 份文件、建立 ${result.embedded_chunks} 個向量。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "知識庫同步失敗。");
    } finally {
      setBusy("");
    }
  }

  const maxFeature = useMemo(
    () => Math.max(1, ...Object.values(stats?.feature_usage ?? {})),
    [stats],
  );

  if (!stats) {
    return <div className="page-shell">{error
      ? <div className="form-error">{error}</div>
      : <div className="page-loading">正在整理管理後台…</div>}</div>;
  }

  return (
    <div className="page-shell admin-page">
      <header className="page-header admin-header">
        <div><span className="header-kicker">Administration</span><h1>{config.app_name} 管理後台</h1><p>管理帳號、AI 使用狀態、可替換知識向量與系統稽核；不提供私人對話內容查閱。</p></div>
        <div className="admin-header-actions">
          <span className={`status-pill ${stats.configured ? "online" : "warning"}`}><i />{stats.configured ? "NVIDIA NIM 已設定" : "尚未設定 API Key"}</span>
          <button className="secondary-button" onClick={() => void refreshAll()} disabled={busy === "refresh"}><RefreshCw size={16} className={busy === "refresh" ? "spin" : ""} />更新資料</button>
        </div>
      </header>

      {(error || notice) && <div className={`admin-flash ${error ? "error" : "success"}`}><span>{error || notice}</span><button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}

      <nav className="admin-tabs" aria-label="管理功能">
        {tabItems.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}><Icon size={17} />{label}</button>)}
      </nav>

      {tab === "overview" && <>
        <div className="stat-grid admin-stat-grid">
          <div className="stat-card"><span className="stat-icon green"><Users size={21} /></span><small>使用者</small><strong>{stats.users.toLocaleString()}</strong><p>{stats.active_users} 位啟用 · {stats.admins} 位管理員</p></div>
          {config.enable_turtle_module && <div className="stat-card"><span className="stat-icon blue"><Turtle size={21} /></span><small>{config.profile_label}</small><strong>{stats.turtles.toLocaleString()}</strong><p>累計建立的示範模組資料</p></div>}
          <div className="stat-card"><span className="stat-icon amber"><MessageSquare size={21} /></span><small>對話／訊息</small><strong>{stats.conversations.toLocaleString()}</strong><p>{stats.message_count} 則訊息 · 今日新增 {stats.conversations_today}</p></div>
          <div className="stat-card"><span className="stat-icon purple"><Zap size={21} /></span><small>今日 AI Requests</small><strong>{stats.ai_requests_today.toLocaleString()}</strong><p>成功率 {stats.ai_success_rate_today == null ? "尚無資料" : `${stats.ai_success_rate_today}%`} · {stats.ai_errors_today} 次錯誤</p></div>
        </div>

        <div className="admin-grid">
          <section className="admin-panel"><div className="panel-title"><span><Activity size={19} /><strong>功能使用分布</strong></span><small>今日</small></div><div className="feature-bars">{Object.entries(stats.feature_usage).length ? Object.entries(stats.feature_usage).map(([feature, count]) => <div className="feature-row" key={feature}><span>{featureLabels[feature] ?? feature}</span><div><i style={{ width: `${Math.max(7, count / maxFeature * 100)}%` }} /></div><strong>{count}</strong></div>) : <div className="empty-inline">今天還沒有 AI 請求</div>}</div></section>
          <section className="admin-panel"><div className="panel-title"><span><Bot size={19} /><strong>模型與知識狀態</strong></span><span className={`status-pill mini ${stats.configured ? "online" : "warning"}`}><i />{stats.configured ? "已設定" : "待設定"}</span></div><div className="model-status"><div><small>文字聊天</small><strong>{stats.model}</strong></div><div><small>圖片分析</small><strong>{stats.vision_model}</strong></div><div><small>RAG Embedding</small><strong>{stats.embedding_model}</strong></div><div className="kb-progress"><span><b>{stats.embedded_chunks}</b> / {stats.knowledge_chunks} 個知識片段已有向量</span><div><i style={{ width: `${stats.knowledge_chunks ? stats.embedded_chunks / stats.knowledge_chunks * 100 : 0}%` }} /></div></div><div className="model-metrics"><span><Clock3 size={16} />最近延遲 <b>{stats.last_latency_ms ? `${stats.last_latency_ms} ms` : "尚無資料"}</b></span><span><Zap size={16} />最近成功 <b>{formatDate(stats.last_success_at)}</b></span></div></div></section>
        </div>

        <section className="token-panel"><div><small>今日 Input Tokens</small><strong>{stats.input_tokens_today.toLocaleString()}</strong></div><div><small>今日 Output Tokens</small><strong>{stats.output_tokens_today.toLocaleString()}</strong></div><div><small>今日 API Cost</small><strong>{stats.cost_configured ? `$${(stats.estimated_cost_today ?? 0).toFixed(4)}` : "未設定"}</strong></div><p>後台僅呈現彙總與技術中繼資料，不會顯示使用者的私人訊息內容。</p></section>
      </>}

      {tab === "users" && <section className="admin-section">
        <div className="admin-toolbar"><div className="admin-search"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { setUserPage(1); void loadUsers(1); } }} placeholder="搜尋名稱或 Email" /></div><button className="secondary-button" onClick={() => { setUserPage(1); void loadUsers(1); }}>搜尋</button><span>共 {users?.total ?? 0} 位</span></div>
        <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>帳號</th><th>權限／狀態</th><th>資料量</th><th>最後登入</th><th>操作</th></tr></thead><tbody>{users?.items.map((item) => <tr key={item.id}><td><div className="table-user"><span>{item.display_name.slice(0, 1)}</span><div><strong>{item.display_name}</strong><small>{item.email}</small></div></div></td><td><div className="badge-row"><span className={`admin-badge ${item.role}`}>{item.role === "admin" ? "管理員" : "一般使用者"}</span><span className={`admin-badge ${item.is_active ? "active" : "disabled"}`}>{item.is_active ? "啟用" : "停用"}</span></div></td><td><small>{config.enable_turtle_module && <>{item.turtle_count} 份 Profile · </>}{item.conversation_count} 對話<br />{item.message_count} 訊息 · {item.ai_request_count} AI 請求</small></td><td><small>{formatDate(item.last_login_at)}<br />建立於 {new Date(item.created_at).toLocaleDateString("zh-TW")}</small></td><td>{item.id === user?.id ? <span className="self-label"><ShieldCheck size={15} />目前帳號</span> : <div className="table-actions"><button title={item.role === "admin" ? "降為一般使用者" : "設為管理員"} onClick={() => void updateUser(item, { role: item.role === "admin" ? "user" : "admin" })} disabled={busy === `user-${item.id}`}><UserCog size={16} /></button><button className={item.is_active ? "danger" : "success"} title={item.is_active ? "停用帳號" : "啟用帳號"} onClick={() => void updateUser(item, { is_active: !item.is_active })} disabled={busy === `user-${item.id}`}>{item.is_active ? <UserX size={16} /> : <UserCheck size={16} />}</button></div>}</td></tr>)}</tbody></table>{!users?.items.length && <div className="empty-inline">找不到符合條件的使用者</div>}</div>
        <div className="admin-pagination"><button disabled={userPage <= 1} onClick={() => { const page = userPage - 1; setUserPage(page); void loadUsers(page); }}>上一頁</button><span>第 {userPage} 頁</span><button disabled={!users || userPage * users.page_size >= users.total} onClick={() => { const page = userPage + 1; setUserPage(page); void loadUsers(page); }}>下一頁</button></div>
      </section>}

      {tab === "usage" && <section className="admin-section">
        <div className="admin-toolbar"><select value={usageStatus} onChange={(event) => { const status = event.target.value; setUsageStatus(status); setUsagePage(1); void loadUsage(1, status); }}><option value="">全部狀態</option><option value="success">成功</option><option value="error">錯誤</option></select><span>共 {usage?.total ?? 0} 筆技術紀錄</span></div>
        <div className="admin-table-wrap"><table className="admin-table usage-table"><thead><tr><th>時間／功能</th><th>使用者</th><th>模型</th><th>Tokens</th><th>延遲</th><th>狀態</th></tr></thead><tbody>{usage?.items.map((item) => <tr key={item.id}><td><strong>{featureLabels[item.feature] ?? item.feature}</strong><small>{formatDate(item.created_at)}<br />{item.request_id}</small></td><td><small>{item.user_email ?? "系統工作"}</small></td><td><small>{item.model}</small></td><td><small>{item.input_tokens ?? "—"} / {item.output_tokens ?? "—"}{item.usage_estimated ? "（估）" : ""}</small></td><td><small>{item.latency_ms == null ? "—" : `${item.latency_ms} ms`}</small></td><td><span className={`admin-badge ${item.status === "success" ? "active" : "disabled"}`}>{statusLabel(item.status)}</span>{item.error_code && <small>{item.error_code}</small>}</td></tr>)}</tbody></table>{!usage?.items.length && <div className="empty-inline">目前沒有符合條件的 AI 紀錄</div>}</div>
        <div className="admin-pagination"><button disabled={usagePage <= 1} onClick={() => { const page = usagePage - 1; setUsagePage(page); void loadUsage(page); }}>上一頁</button><span>第 {usagePage} 頁</span><button disabled={!usage || usagePage * usage.page_size >= usage.total} onClick={() => { const page = usagePage + 1; setUsagePage(page); void loadUsage(page); }}>下一頁</button></div>
      </section>}

      {tab === "knowledge" && <section className="admin-section">
        <div className="admin-toolbar"><div className="knowledge-admin-summary"><Database size={18} /><span><strong>{knowledge?.active_documents ?? 0}</strong> 份啟用文件 · <strong>{knowledge?.embedded_chunks ?? 0}/{knowledge?.chunks ?? 0}</strong> 個有效向量</span></div><button className="primary-button" onClick={() => void syncKnowledge()} disabled={busy === "knowledge"}><RefreshCw size={16} className={busy === "knowledge" ? "spin" : ""} />同步知識庫</button></div>
        <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>文件</th><th>審閱日期</th><th>片段</th><th>向量狀態</th><th>狀態</th></tr></thead><tbody>{knowledge?.items.map((item) => { const complete = item.chunk_count > 0 && item.embedded_chunks === item.chunk_count; return <tr key={item.id}><td><strong>{item.title}</strong><small>{item.slug}</small></td><td><small>{item.reviewed_at}</small></td><td><small>{item.chunk_count}</small></td><td><div className="inline-progress"><div><i style={{ width: `${item.chunk_count ? item.embedded_chunks / item.chunk_count * 100 : 0}%` }} /></div><span>{item.embedded_chunks}/{item.chunk_count}</span></div></td><td><span className={`admin-badge ${item.is_active && complete ? "active" : "disabled"}`}>{!item.is_active ? "停用" : complete ? "就緒" : "待同步"}</span></td></tr>; })}</tbody></table></div>
      </section>}

      {tab === "system" && <>
        <div className="admin-grid system-grid">
          <section className="admin-panel"><div className="panel-title"><span><ServerCog size={19} /><strong>NVIDIA NIM 健康檢查</strong></span><button className="secondary-button compact" onClick={() => void checkProvider()} disabled={busy === "provider"}><RefreshCw size={14} className={busy === "provider" ? "spin" : ""} />立即檢查</button></div>{providerHealth ? <div className="health-result"><div className={providerHealth.reachable ? "healthy" : "unhealthy"}>{providerHealth.reachable ? <CheckCircle2 size={21} /> : <ServerCog size={21} />}<span><strong>{providerHealth.message}</strong><small>{providerHealth.latency_ms == null ? "無延遲資料" : `${providerHealth.latency_ms} ms`} · {formatDate(providerHealth.checked_at)}</small></span></div><ul><li>聊天模型：{providerHealth.chat_model_available ? "可用" : "未列出"}</li><li>圖片模型：{providerHealth.vision_model_available ? "可用" : "未列出"}</li><li>Embedding：{providerHealth.embedding_model_available ? "可用" : "未列出"}</li></ul></div> : <div className="empty-inline">按「立即檢查」驗證金鑰與目前模型清單，不會產生聊天內容。</div>}</section>
          <section className="admin-panel"><div className="panel-title"><span><ShieldCheck size={19} /><strong>系統限制</strong></span><small>{system?.app_env ?? "—"} · {system?.database_backend ?? "—"}</small></div>{system && <div className="system-settings"><div><span>Session</span><strong>{system.session_days} 天</strong></div><div><span>每人 AI 限流</span><strong>{system.ai_requests_per_minute} 次／分</strong></div><div><span>並行限制</span><strong>{system.ai_per_user_concurrency}／人 · {system.ai_global_concurrency}／全站</strong></div><div><span>文字上限</span><strong>{system.max_input_chars.toLocaleString()} 字</strong></div><div><span>圖片限制</span><strong>{Math.round(system.max_image_bytes / 1024 / 1024)} MB × {system.max_images_per_message}</strong></div><div><span>對話 Context</span><strong>最近 {system.context_recent_messages} 則</strong></div></div>}</section>
        </div>
        <section className="admin-section audit-section"><div className="panel-title"><span><History size={19} /><strong>管理操作稽核</strong></span><small>共 {audits?.total ?? 0} 筆</small></div><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>時間</th><th>管理員</th><th>操作</th><th>目標</th><th>摘要</th></tr></thead><tbody>{audits?.items.map((item) => <tr key={item.id}><td><small>{formatDate(item.created_at)}</small></td><td><small>{item.actor_email ?? "已刪除帳號"}</small></td><td><strong>{item.action}</strong></td><td><small>{item.target_type}<br />{item.target_id ?? "—"}</small></td><td><small>{JSON.stringify(item.details)}</small></td></tr>)}</tbody></table>{!audits?.items.length && <div className="empty-inline">尚無管理操作紀錄</div>}</div></section>
      </>}
    </div>
  );
}
