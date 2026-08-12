import { render, screen } from "@testing-library/react";
import { MarkdownMessage } from "./MarkdownMessage";

describe("MarkdownMessage", () => {
  it("renders GFM content and removes unsafe raw HTML", () => {
    const { container } = render(
      <MarkdownMessage content={'## 建議\n\n| 項目 | 狀態 |\n|---|---|\n| UVB | 正常 |\n\n<script>alert("xss")</script>'} />,
    );
    expect(screen.getByRole("heading", { name: "建議" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(container.querySelector("script")).not.toBeInTheDocument();
  });

  it("renders citation links with safe external attributes", () => {
    render(
      <MarkdownMessage
        content="依知識庫資料調整。"
        citations={[{ document_id: "d1", chunk_id: "c1", title: "UVB 指南", source_name: "VCA", source_url: "https://example.com", section: "距離", rank: 1, score: 0.9 }]}
      />,
    );
    const link = screen.getByRole("link", { name: /UVB 指南/ });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("renders local knowledge citations without an empty link", () => {
    render(
      <MarkdownMessage
        content="依內部文件回答。"
        citations={[{ document_id: "d2", chunk_id: "c2", title: "校務辦法", source_name: "本機知識庫", source_url: "", section: "流程", rank: 1, score: 0.9 }]}
      />,
    );
    expect(screen.getByText("校務辦法")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /校務辦法/ })).not.toBeInTheDocument();
  });
});
