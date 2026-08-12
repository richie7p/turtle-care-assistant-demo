import { ExternalLink } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { Citation } from "../types";

export function MarkdownMessage({ content, citations = [] }: { content: string; citations?: Citation[] }) {
  return (
    <div className="markdown-message">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{content}</ReactMarkdown>
      {citations.length > 0 && (
        <div className="citation-list">
          <div className="citation-label">參考資料</div>
          {citations.map((citation) => citation.source_url ? (
            <a key={citation.chunk_id} href={citation.source_url} target="_blank" rel="noreferrer" className="citation-card">
              <span className="citation-index">{citation.rank}</span>
              <span><strong>{citation.title}</strong><small>{citation.source_name} · {citation.section}</small></span>
              <ExternalLink size={15} />
            </a>
          ) : (
            <div key={citation.chunk_id} className="citation-card">
              <span className="citation-index">{citation.rank}</span>
              <span><strong>{citation.title}</strong><small>{citation.source_name} · {citation.section}</small></span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
