import { api, APIError, setCSRFToken, streamMessage } from "./api";

describe("api client", () => {
  it("adds CSRF token to mutation requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    setCSRFToken("csrf-test");
    await api("/settings", { method: "PATCH", body: JSON.stringify({ theme: "light" }) });
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get("X-CSRF-Token")).toBe("csrf-test");
    vi.unstubAllGlobals();
  });

  it("turns API failures into friendly errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "請先登入。" }), { status: 401 })));
    await expect(api("/turtles")).rejects.toEqual(expect.objectContaining<Partial<APIError>>({ message: "請先登入。", status: 401 }));
    vi.unstubAllGlobals();
  });

  it("parses all SSE tokens and completion events", async () => {
    const sse = [
      'event: meta\ndata: {"assistant_message_id":"answer-1"}\n\n',
      'event: token\ndata: {"delta":"第一段"}\n\n',
      'event: token\ndata: {"delta":"第二段"}\n\n',
      'event: done\ndata: {"message_id":"answer-1"}\n\n',
    ].join("");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(sse, { status: 200 })));
    const tokens: string[] = [];
    let completed = false;
    await streamMessage("conversation-1", { content: "測試", attachment_ids: [] }, {
      onToken: (token) => tokens.push(token),
      onDone: () => { completed = true; },
    });
    expect(tokens).toEqual(["第一段", "第二段"]);
    expect(completed).toBe(true);
    vi.unstubAllGlobals();
  });

  it("reports a stream that closes without done or error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      'event: token\ndata: {"delta":"部分回答"}\n\n',
      { status: 200 },
    )));
    const errors: string[] = [];
    await streamMessage("conversation-1", { content: "測試", attachment_ids: [] }, {
      onError: (message) => errors.push(message),
    });
    expect(errors[0]).toContain("連線已中斷");
    vi.unstubAllGlobals();
  });
});
