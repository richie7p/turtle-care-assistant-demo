# 烏龜飼養小助手：技術稽核修復紀錄

更新日期：2026-10-04。原始稽核採 2026-10-03 快照；本輪以實際依賴樹及執行結果核對，不將重複 finding 視為不同漏洞。

## PDF 項目對照（第 31-32 頁）

| PDF 項目 | 優先級 | 本輪狀態 |
| --- | --- | --- |
| Starlette／Pillow／multipart 已公告依賴 | P1 | 已更新相容版本；後端與上傳／附件回歸測試通過 |
| 知識文件尚未由獸醫審閱 | P1 | 維持示範資料定位；待具資格專家審閱，不能以程式修改宣告完成 |
| SQLite JSON vectors／process-local 狀態的擴展限制 | P2 | 已整理限制與驗證順序；多程序架構與 PostgreSQL 整合仍待實作及環境測試 |
| NIM 模型忠實度、引用、失敗與成本限制 | P2 | 已完成真實 Chat／Vision／Embedding／fallback 小樣本流程；領域品質、成本與正式限制仍待驗證 |
| Cloud object store／production auth／備份及事件處理 | P2 | 待隔離雲端環境與演練 |
| undici 與 Vitest 開發依賴公告 | P2 | 已更新；npm 全樹掃描為零項 |

PDF 重複出現的依賴 finding 合併追蹤；另同步修正與核心版共用的跨平台 E2E 設定。

## 已完成的修改

| 項目 | 修改 | 驗證方式 |
| --- | --- | --- |
| Python 依賴 | FastAPI 0.142.2、Starlette 1.7.0、Pillow 12.3.0、python-multipart 0.0.32；更新 pytest 與 pytest-asyncio | 相容依賴解析、pytest、pip-audit |
| 圖片上傳 | `Image.open` 僅啟用 JPEG、PNG、WebP decoder，於驗證及解碼前排除其他格式 | 三格式往返、偽裝 GIF 拒絕測試 |
| 私人附件 | 確認依賴升級後部分檔案讀取仍檢查登入與所有權 | 206／416 回應、未登入 401、跨帳號 404 |
| 前端依賴 | 以已驗證版本取代 `latest`；Vitest 4.1.11；更新 undici 鎖定版本；React 建置外掛歸入 devDependencies | `npm ci`、`npm audit`、型別檢查、測試、建置 |
| E2E 設定 | 伺服器與測試共用 edition 預設值；Python 路徑依作業系統選擇並支援空白；使用專案 Chromium | 預設 edition 與切換 edition 的桌機／手機流程 |
| CI | 保留 Windows／Linux／macOS；新增型別檢查、npm／Python 依賴掃描、瀏覽器安裝；Python cache 同時追蹤兩份 requirements | Pull request 的 Actions 結果 |

CI 會在依賴掃描命中公告時阻擋，不忽略 advisory。npm 掃描包含開發工具；Python 掃描包含 requirements-dev 及其 production requirements。

## 重跑驗證

從 repository 根目錄完成 README 的安裝步驟，再執行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.cli validate-knowledge
Set-Location ..\frontend
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
npm.cmd audit --audit-level=moderate
```

若要測另一個 edition，在 `frontend/` 設定 `$env:E2E_TURTLE_MODULE='false'`，再執行 `npm.cmd run test:e2e`；完成後用 `Remove-Item Env:E2E_TURTLE_MODULE` 恢復預設。

Python 掃描可在獨立工具環境安裝 `pip-audit==2.10.1`，從根目錄執行 `python -m pip_audit -r backend/requirements-dev.txt`。npm 與 pip advisory 資料會更新，零項結果只代表當次掃描沒有已知命中。

## 後續優先順序

1. 真實 NVIDIA Chat、Vision、Embedding 連線與小樣本流程已測；完整輸出品質與費用驗證仍待完成。E2E 明確清空 AI Key；Fake Provider 的測試結果不代表雲端模型品質。
2. 12 份示範知識仍需具資格的獸醫／資料負責人逐份審閱；照片分析與危險症狀的真實模型輸出需另做領域驗證。
3. 正式部署的 HTTPS、Session Secret、備份／還原、可信任 Origin 驗證。
4. 維持單程序 SQLite 部署；多 worker／多實例前完成 PostgreSQL migration、共享限流與並行隔離測試。

首輪依賴修復未操作 production 資料或呼叫真實 Provider；後續授權 NVIDIA smoke 見下方紀錄。不能以自動測試或依賴掃描替代正式環境驗收。

## 修補依據

- [Starlette Range header 公告](https://github.com/Kludex/starlette/security/advisories/GHSA-7f5h-v6xp-fcq8)
- [Pillow PSD 解碼公告](https://github.com/python-pillow/Pillow/security/advisories/GHSA-pwv6-vv43-88gr)
- [python-multipart 解析公告](https://github.com/Kludex/python-multipart/security/advisories/GHSA-5rvq-cxj2-64vf)
- [Vitest mock 路徑公告](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)

## 本輪本機驗證結果

2026-10-04，Windows／Node.js 22.23.2／Python 3.11.16。首輪後端 46 項、前端 7 項測試通過；預設及另一個 edition 各 2 項桌機／手機 E2E 通過。型別檢查、production build、migration 與知識文件結構檢查通過。npm 全樹與升級後 Python 安裝環境的 advisory 掃描均為零項。

Python 測試仍有 Starlette 對 httpx TestClient 及舊 status 常數的棄用警告，未影響結果。跨作業系統驗證由本 PR 的 CI 執行；此處的本機結果不代表真實 Provider 或 production 驗證。

## 授權真實 API 後續測試

已補上 [NVIDIA 真實測試紀錄](LIVE-NVIDIA-TEST.md) 與可手動重跑的工具。詳列首次失敗、修正、最後一輪結果及驗證限制；不得由小樣本通過推論醫療或飼養正確率。

## Content and function acceptance update

See [the 2026-10-04 acceptance record](CONTENT-FUNCTION-ACCEPTANCE.md) for the additional content review, fixes, regression cases and limits. Earlier counts above describe the audit baseline.
