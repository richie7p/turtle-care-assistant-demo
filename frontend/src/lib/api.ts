let csrfToken = "";

export class APIError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function setCSRFToken(token: string) {
  csrfToken = token;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (options.method && !["GET", "HEAD"].includes(options.method.toUpperCase()) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(`/api/v1${path}`, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    let message = "操作失敗，請稍後再試。";
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : message;
    } catch {
      // Keep friendly fallback.
    }
    throw new APIError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function uploadImage(file: File, conversationId?: string) {
  const body = new FormData();
  body.append("file", file);
  const query = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
  return api<import("../types").Attachment>(`/attachments${query}`, { method: "POST", body });
}

interface StreamCallbacks {
  onMeta?: (data: Record<string, string>) => void;
  onToken?: (delta: string) => void;
  onCitations?: (items: import("../types").Citation[], status: string) => void;
  onUsage?: (data: Record<string, number | boolean>) => void;
  onDone?: (data: Record<string, string>) => void;
  onError?: (message: string, code?: string) => void;
}

export async function streamMessage(
  conversationId: string,
  payload: { content: string; attachment_ids: string[] },
  callbacks: StreamCallbacks,
) {
  const response = await fetch(`/api/v1/conversations/${conversationId}/messages/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
  if (!response.ok || !response.body) {
    let message = "無法開始 AI 回應。";
    try {
      message = (await response.json()).detail ?? message;
    } catch {
      // Keep friendly fallback.
    }
    throw new APIError(message, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminalEvent = false;

  function handleBlock(block: string) {
    if (!block.trim()) return;
    let event = "message";
    let data = "{}";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data = line.slice(5).trim();
    }
    let parsed: Record<string, any>;
    try {
      parsed = JSON.parse(data);
    } catch {
      throw new APIError("AI 串流資料格式不完整，請重新載入對話。", 502);
    }
    if (event === "meta") callbacks.onMeta?.(parsed);
    if (event === "token") callbacks.onToken?.(parsed.delta ?? "");
    if (event === "citations") callbacks.onCitations?.(parsed.items ?? [], parsed.status);
    if (event === "usage") callbacks.onUsage?.(parsed);
    if (event === "done") { terminalEvent = true; callbacks.onDone?.(parsed); }
    if (event === "error") { terminalEvent = true; callbacks.onError?.(parsed.message, parsed.code); }
  }

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    blocks.forEach(handleBlock);
    if (done) break;
  }
  if (buffer.trim()) handleBlock(buffer);
  if (!terminalEvent) {
    callbacks.onError?.("連線已中斷，正在保留已收到的回答；請重新載入對話。", "stream_interrupted");
  }
}
