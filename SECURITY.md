# Security Policy

## Reporting a vulnerability

請使用 GitHub 的 Private Vulnerability Reporting 或 Security Advisory 回報安全問題。不要在公開 issue 貼出 API Key、Session Cookie、資料庫、私人對話、可利用的完整攻擊細節或使用者資料。

回報內容建議包含：

- 受影響版本與部署方式
- 可重現步驟
- 預期與實際行為
- 可能影響
- 已移除所有真實憑證與私人資料的證據

## Secrets

NVIDIA NIM API Key 只應存在未被 Git 追蹤的 `.env` 或部署平台的秘密管理服務。若 Key 曾經進入 commit、issue、截圖或聊天，請立即到 NVIDIA 撤銷並建立新 Key；只從 Git 歷史刪除文字並不足以恢復安全。

