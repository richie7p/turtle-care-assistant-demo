import {
  BookOpenCheck, Camera, ChevronDown, GitCompareArrows, ImagePlus, Lightbulb, ListChecks,
  Menu, MessageSquarePlus, MoreHorizontal, Pencil, SearchCheck, Send, Sparkles, Trash2,
  Turtle as TurtleIcon, X,
} from "lucide-react";
import { ChangeEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { MarkdownMessage } from "../components/MarkdownMessage";
import { api, streamMessage, uploadImage } from "../lib/api";
import { useAppConfig } from "../context/ConfigContext";
import type { Citation, Conversation, ConversationDetail, Message, Turtle, UserSettings } from "../types";

const turtleQuickPrompts = [
  { icon: TurtleIcon, title: "我的烏龜", text: "根據我的龜龜資料，檢查目前飼養方式有哪些可以改善？", tone: "green" },
  { icon: Camera, title: "環境分析", text: "請分析我接下來上傳的飼養環境照片，列出值得改善的地方。", tone: "blue" },
  { icon: Lightbulb, title: "飼養建議", text: "請依照季節整理一份日常照顧與觀察清單。", tone: "amber" },
  { icon: Sparkles, title: "水質與 UVB", text: "請說明水質與 UVB 設備最容易忽略的重點。", tone: "purple" },
];

const genericQuickPrompts = [
  { icon: BookOpenCheck, title: "知識摘要", text: "請整理知識庫中與這個主題最相關的重點，並附上來源。", tone: "green" },
  { icon: SearchCheck, title: "查詢規章", text: "請依知識庫回答我的問題；若資料不足，請明確列出還缺少什麼。", tone: "blue" },
  { icon: GitCompareArrows, title: "比較內容", text: "比較知識庫中的相關說法，整理共同點、差異與需要確認之處。", tone: "amber" },
  { icon: ListChecks, title: "執行清單", text: "把相關知識整理成一份可以逐項執行與檢查的清單。", tone: "purple" },
];

function groupLabel(dateString: string) {
  const date = new Date(dateString); const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const itemDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const days = Math.round((today.getTime() - itemDay.getTime()) / 86400000);
  if (days === 0) return "今天"; if (days === 1) return "昨天"; if (days < 7) return "最近 7 天"; return "更早";
}

export function ChatPage() {
  const { conversationId } = useParams(); const navigate = useNavigate();
  const { config } = useAppConfig();
  const quickPrompts = config.enable_turtle_module ? turtleQuickPrompts : genericQuickPrompts;
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [turtles, setTurtles] = useState<Turtle[]>([]);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [draft, setDraft] = useState(""); const [files, setFiles] = useState<File[]>([]);
  const [streaming, setStreaming] = useState(false); const [error, setError] = useState("");
  const [ragStatus, setRagStatus] = useState(""); const [newTurtleId, setNewTurtleId] = useState("");
  const [chatNavOpen, setChatNavOpen] = useState(false); const endRef = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function loadLists() {
    const [conversationData, turtleData, userSettings] = await Promise.all([
      api<Conversation[]>("/conversations"),
      config.enable_turtle_module ? api<Turtle[]>("/turtles") : Promise.resolve([]),
      api<UserSettings>("/settings"),
    ]);
    setConversations(conversationData); setTurtles(turtleData);
    setNewTurtleId((current) => current || userSettings.default_turtle_id || turtleData[0]?.id || "");
  }
  useEffect(() => { void loadLists(); }, [config.enable_turtle_module]);
  useEffect(() => {
    if (!conversationId) { setDetail(null); return; }
    api<ConversationDetail>(`/conversations/${conversationId}`).then(setDetail).catch((err) => setError(err.message));
  }, [conversationId]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: streaming ? "auto" : "smooth" }); }, [detail?.messages, streaming]);

  async function reloadDetail(id = detail?.id) {
    if (!id) return;
    try {
      setDetail(await api<ConversationDetail>(`/conversations/${id}`));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法重新載入對話。");
    }
  }

  const grouped = useMemo(() => {
    const map = new Map<string, Conversation[]>();
    for (const item of conversations) { const key = groupLabel(item.updated_at); map.set(key, [...(map.get(key) ?? []), item]); }
    return map;
  }, [conversations]);

  function addFiles(event: ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? []).filter((file) => file.type.startsWith("image/"));
    setFiles((current) => [...current, ...picked].slice(0, 4)); event.target.value = "";
  }

  async function ensureConversation() {
    if (conversationId && detail) return detail.id;
    const created = await api<Conversation>("/conversations", {
      method: "POST", body: JSON.stringify({ turtle_id: config.enable_turtle_module ? newTurtleId || null : null }),
    });
    setConversations((current) => [created, ...current]); navigate(`/chat/${created.id}`, { replace: true });
    setDetail({ ...created, messages: [] }); return created.id;
  }

  async function submit() {
    const content = draft.trim(); if (!content || streaming) return;
    setError(""); setRagStatus(""); setStreaming(true);
    try {
      const id = await ensureConversation();
      const attachments = await Promise.all(files.map((file) => uploadImage(file, id)));
      const now = new Date().toISOString();
      const optimisticUser: Message = { id: `local-user-${Date.now()}`, user_id: "", conversation_id: id, role: "user", content, status: "complete", created_at: now, attachments, citations: [] };
      const optimisticAssistant: Message = { id: `local-ai-${Date.now()}`, user_id: "", conversation_id: id, role: "assistant", content: "", status: "streaming", created_at: now, attachments: [], citations: [] };
      setDetail((current) => current ? { ...current, messages: [...current.messages, optimisticUser, optimisticAssistant] } : current);
      setDraft(""); setFiles([]);
      let assistantId = optimisticAssistant.id; let citations: Citation[] = [];
      await streamMessage(id, { content, attachment_ids: attachments.map((item) => item.id) }, {
        onMeta: (data) => { assistantId = data.assistant_message_id; },
        onToken: (delta) => setDetail((current) => current ? { ...current, messages: current.messages.map((message) => message.id === optimisticAssistant.id || message.id === assistantId ? { ...message, id: assistantId, content: message.content + delta } : message) } : current),
        onCitations: (items, status) => { citations = items; setRagStatus(status); setDetail((current) => current ? { ...current, messages: current.messages.map((message) => message.id === optimisticAssistant.id || message.id === assistantId ? { ...message, citations: items } : message) } : current); },
        onDone: (data) => setDetail((current) => current ? { ...current, title: data.conversation_title || current.title, messages: current.messages.map((message) => message.id === assistantId || message.id === optimisticAssistant.id ? { ...message, id: data.message_id || assistantId, status: "complete", citations } : message) } : current),
        onError: (message) => { setError(message); setDetail((current) => current ? { ...current, messages: current.messages.map((item) => item.id === assistantId || item.id === optimisticAssistant.id ? { ...item, status: "error" } : item) } : current); },
      });
      await Promise.all([loadLists(), reloadDetail(id)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "訊息傳送失敗。");
      if (detail?.id) await reloadDetail(detail.id);
    }
    finally { setStreaming(false); }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); }
  }

  async function changeTurtle(value: string) {
    if (!detail) { setNewTurtleId(value); return; }
    const updated = await api<Conversation>(`/conversations/${detail.id}`, { method: "PATCH", body: JSON.stringify({ turtle_id: value || null }) });
    setDetail({ ...detail, ...updated }); void loadLists();
  }

  async function renameConversation() {
    if (!detail) return; const title = window.prompt("新的對話名稱", detail.title)?.trim(); if (!title) return;
    const updated = await api<Conversation>(`/conversations/${detail.id}`, { method: "PATCH", body: JSON.stringify({ title }) });
    setDetail({ ...detail, ...updated }); void loadLists();
  }
  async function removeConversation() {
    if (!detail || !window.confirm("確定刪除這個對話與所有訊息嗎？")) return;
    await api(`/conversations/${detail.id}`, { method: "DELETE" }); await loadLists(); navigate("/chat");
  }

  return (
    <div className="chat-page">
      <button className="chat-nav-toggle" onClick={() => setChatNavOpen(!chatNavOpen)} aria-label="顯示對話記錄"><Menu size={20} /></button>
      <aside className={`conversation-sidebar ${chatNavOpen ? "open" : ""}`}>
        <div className="conversation-heading"><strong>對話紀錄</strong><button className="icon-button" onClick={() => setChatNavOpen(false)}><X size={18} /></button></div>
        <button className="new-chat-button" onClick={() => { navigate("/chat"); setChatNavOpen(false); }}><MessageSquarePlus size={18} /> 新對話</button>
        <div className="conversation-list">
          {conversations.length === 0 && <div className="empty-side"><MessageSquarePlus size={22} /><span>還沒有對話</span></div>}
          {Array.from(grouped.entries()).map(([label, items]) => <div className="conversation-group" key={label}><span>{label}</span>{items.map((item) => <button key={item.id} className={item.id === conversationId ? "selected" : ""} onClick={() => { navigate(`/chat/${item.id}`); setChatNavOpen(false); }}><span className="conversation-title">{item.title}</span>{item.turtle_name && <small>🐢 {item.turtle_name}</small>}</button>)}</div>)}
        </div>
      </aside>

      <section className="chat-workspace">
        <header className="chat-header">
          <div><span className="header-kicker">{config.assistant_name}</span><h1>{detail?.title ?? "今天想問什麼？"}</h1></div>
          <div className="header-actions">
            {config.enable_turtle_module && <label className="turtle-select"><TurtleIcon size={17} /><span>正在詢問</span><select value={detail?.turtle_id ?? newTurtleId} onChange={(e) => void changeTurtle(e.target.value)}><option value="">未指定龜龜</option>{turtles.map((turtle) => <option key={turtle.id} value={turtle.id}>{turtle.name}</option>)}</select><ChevronDown size={14} /></label>}
            {detail && <><button className="icon-button" onClick={() => void renameConversation()} title="重新命名"><Pencil size={17} /></button><button className="icon-button danger-hover" onClick={() => void removeConversation()} title="刪除對話"><Trash2 size={17} /></button></>}
          </div>
        </header>

        <div className="messages-scroll">
          {!detail?.messages.length ? (
            <div className="chat-welcome">
              <div className="welcome-orbit"><div className="welcome-turtle">{config.app_icon}</div></div>
              <h2>{config.welcome_title}</h2><p>{config.welcome_description}</p>
              <div className="quick-grid">{quickPrompts.map(({ icon: Icon, title, text, tone }) => <button key={title} className={`quick-card ${tone}`} onClick={() => setDraft(text)}><span><Icon size={20} /></span><strong>{title}</strong><small>{text}</small></button>)}</div>
              {config.enable_turtle_module && turtles.length === 0 && <div className="welcome-tip">先到「{config.profile_label}」建立資料，回答會更貼近實際狀況。</div>}
            </div>
          ) : (
            <div className="message-list">{detail.messages.map((message) => (
              <article className={`message-row ${message.role}`} key={message.id}>
                  <div className="message-avatar">{message.role === "assistant" ? config.app_icon : "你"}</div>
                <div className="message-body">
                  <div className="message-name">{message.role === "assistant" ? config.assistant_name : "你"}</div>
                  {message.attachments.length > 0 && <div className="message-images">{message.attachments.map((attachment) => <img src={attachment.url ?? `/api/v1/attachments/${attachment.id}`} alt={attachment.original_name} key={attachment.id} />)}</div>}
                  {message.role === "assistant" ? <MarkdownMessage content={message.content || (message.status === "streaming" ? "正在整理建議…" : "這次回應沒有完整顯示，可能是瀏覽器連線短暫中斷。")} citations={message.citations} /> : <p>{message.content}</p>}
                  {message.status === "streaming" && <span className="typing-dots"><i /><i /><i /></span>}
                  {message.role === "assistant" && ["error", "interrupted"].includes(message.status) && <button className="retry-message" onClick={() => void reloadDetail()}>重新載入已保存的回答</button>}
                </div>
              </article>
            ))}<div ref={endRef} /></div>
          )}
        </div>

        <footer className="composer-wrap">
          {error && <div className="chat-error"><span>{error}</span><button onClick={() => setError("")}><X size={15} /></button></div>}
          {ragStatus === "unavailable" && <div className="rag-notice">知識庫暫時無法連線，本次回答沒有引用資料。</div>}
          {files.length > 0 && <div className="file-previews">{files.map((file, index) => <div key={`${file.name}-${index}`}><img src={URL.createObjectURL(file)} alt={file.name} /><button onClick={() => setFiles(files.filter((_, i) => i !== index))}><X size={14} /></button></div>)}</div>}
          <div className="composer">
            <button className="attach-button" onClick={() => fileInput.current?.click()} disabled={streaming} title="上傳圖片"><ImagePlus size={21} /></button>
            <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden onChange={addFiles} />
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={onKeyDown} placeholder={config.enable_turtle_module ? "詢問水質、UVB、飲食，或上傳環境照片…" : `詢問${config.knowledge_label}內容，或上傳圖片…`} rows={1} maxLength={8000} disabled={streaming} aria-label="訊息輸入" />
            <button className="send-button" onClick={() => void submit()} disabled={!draft.trim() || streaming} aria-label="傳送訊息"><Send size={19} /></button>
          </div>
          <div className="composer-note">{config.disclaimer}</div>
        </footer>
      </section>
    </div>
  );
}
