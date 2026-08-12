import { BookOpen, ExternalLink, Search, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useAppConfig } from "../context/ConfigContext";
import type { KnowledgeDocument } from "../types";

export function KnowledgePage() {
  const { config } = useAppConfig();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]); const [search, setSearch] = useState(""); const [error, setError] = useState("");
  useEffect(() => { api<KnowledgeDocument[]>("/knowledge").then(setDocuments).catch((err) => setError(err.message)); }, []);
  const filtered = useMemo(() => documents.filter((doc) => `${doc.title} ${doc.description} ${doc.tags.join(" ")}`.toLowerCase().includes(search.toLowerCase())), [documents, search]);
  return <div className="page-shell"><header className="page-header knowledge-header"><div><span className="header-kicker">Knowledge base</span><h1>{config.knowledge_label}</h1><p>AI 回答會優先檢索這些資料，並在有足夠相關性時附上來源。</p></div><div className="trust-chip"><ShieldCheck size={18} /> 保留文件名稱與來源資訊</div></header>
    <div className="search-box"><Search size={19} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={`搜尋${config.knowledge_label}…`} /></div>
    {error && <div className="form-error">{error}</div>}
    <div className="knowledge-summary"><div><BookOpen size={22} /><span><strong>{documents.length}</strong> 份知識文件</span></div><p>{config.disclaimer}</p></div>
    <div className="knowledge-grid">{filtered.map((doc, index) => <article className="knowledge-card" key={doc.id}><div className={`knowledge-icon tone-${index % 4}`}><BookOpen size={21} /></div><div className="knowledge-card-head"><span>{doc.chunk_count} 個檢索片段</span>{doc.reviewed_at && <span>審閱 {doc.reviewed_at}</span>}</div><h2>{doc.title}</h2><p>{doc.description}</p><div className="tag-row">{doc.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>{doc.source_url ? <a href={doc.source_url} target="_blank" rel="noreferrer">{doc.source_name}<ExternalLink size={15} /></a> : <div className="knowledge-source">{doc.source_name}</div>}</article>)}</div>
    {!error && filtered.length === 0 && <div className="empty-state-card compact"><Search size={28} /><h2>找不到符合的主題</h2><p>換個關鍵字，或直接到 AI 對話描述你的問題。</p></div>}
  </div>;
}
