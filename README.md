# 🐢 烏龜飼養小助手 — NVIDIA NIM RAG 實力示範

**繁體中文** | [English](README.en.md)

[![CI](https://github.com/richie7p/turtle-care-assistant-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/richie7p/turtle-care-assistant-demo/actions/workflows/ci.yml)

這是 `NVIDIA NIM RAG Platform` 的完整領域示範版，用烏龜飼養呈現同一套架構如何結合 Profile、私有圖片、Vision、RAG、醫療安全規則與管理後台。

若要改造成學校、公司或其他主題的助理，請從不含領域資料的 [NVIDIA NIM RAG Platform 系統架構版](https://github.com/richie7p/nvidia-nim-rag-platform) 開始。

下載者必須自行申請並填入 NVIDIA NIM API Key；repository 不包含作者的 Key、帳號、資料庫或測試密碼。

## 示範內容

- 多隻烏龜 Profile：物種、水龜／陸龜、體型、環境、UVB、加熱與飲食
- 對話指定龜龜，自動把 Profile 注入 AI Context
- JPEG／PNG／WebP 圖片分析、EXIF 移除、尺寸與數量限制
- 12 份繁體中文示範知識：水龜、陸龜、UVB、水質、溫濕度、過濾、曬背與飲食
- 回答標示實際使用的知識文件，沒有合格 RAG 結果時不製造來源
- 照片只能描述可觀察現象，不會僅憑圖片確診
- 出血、重傷、呼吸異常、長期拒食等情況才自然建議爬蟲類獸醫
- 使用者／對話／龜龜／附件完整權限隔離
- 後台營運總覽、AI 紀錄、知識同步、NIM 健康檢查與管理稽核

## 安裝需求

- Git
- Python 3.11（請確認 `python --version`）
- Node.js 22.22.2 以上的 22.x LTS（也支援 24.15.0 以上的 24.x 與 26 以上）
- 可連線至 `https://integrate.api.nvidia.com`
- 自己的 NVIDIA NIM API Key；前往 [NVIDIA Build](https://build.nvidia.com/mistralai/ministral-14b-instruct-2512) 登入並選擇 **Generate API Key**

Hosted NIM 由 NVIDIA 雲端執行，安裝本專案不需要 NVIDIA GPU 或本機模型。NVIDIA 免費端點可能有額度與流量限制，實際條款以 NVIDIA 頁面為準。

## Windows 快速開始

```powershell
git clone https://github.com/richie7p/turtle-care-assistant-demo.git
Set-Location turtle-care-assistant-demo
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Set-Location frontend
npm.cmd ci
Set-Location ..
Copy-Item .env.example .env
```

先產生 Session Secret：

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

把輸出結果與自己的 NVIDIA Key 填入 `.env`：

```env
SESSION_SECRET=請換成至少32字元的隨機字串
AI_API_KEY=你的_NVIDIA_NIM_API_Key
```

初始化資料庫、建立管理員並同步示範知識：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.cli init-db
..\.venv\Scripts\python.exe -m app.cli create-admin
..\.venv\Scripts\python.exe -m app.cli validate-knowledge
..\.venv\Scripts\python.exe -m app.cli sync-knowledge
Set-Location ..
.\start.cmd
```

`start.cmd` 會自動建置前端、執行 migration 並啟動 FastAPI，不必直接執行可能被 Execution Policy 阻擋的 `.ps1`。開啟 <http://127.0.0.1:8000>；本專案不提供預設帳密。

## macOS／Linux 快速開始

```bash
git clone https://github.com/richie7p/turtle-care-assistant-demo.git
cd turtle-care-assistant-demo
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
cd frontend
npm ci
cd ..
cp .env.example .env
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

把最後一行輸出的 Secret 與自己的 NVIDIA Key 填入 `.env`，再執行：

```bash
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m app.cli init-db
../.venv/bin/python -m app.cli create-admin
../.venv/bin/python -m app.cli validate-knowledge
../.venv/bin/python -m app.cli sync-knowledge
cd ..
bash scripts/start.sh
```

開啟 <http://127.0.0.1:8000>。若要讓腳本可直接執行，可另外執行 `chmod +x scripts/start.sh`。

## 第一次使用與驗收

1. 瀏覽 <http://127.0.0.1:8000/api/health>，確認 `status` 是 `ok`、`configured` 是 `true`。
2. 使用剛建立的管理員登入，在管理後台執行 NVIDIA Provider 檢查，確認 Chat、Vision 與 Embedding 模型可用。
3. 註冊一個一般測試帳號、新增烏龜 Profile，建立對話並選擇該烏龜。
4. 詢問「UVB 燈有什麼作用？」之類的示範文件問題，確認繁中串流回答與引用卡片。
5. 上傳不含私人資訊的測試圖片，確認圖片分析完成；醫療描述不得只依照片確診。

`/api/health` 只會回報是否已填入 Key，不會驗證 Key 是否有效；真實連線與模型品質以 Provider 檢查和上述 Smoke Test 為準。

## 如何證明它不只適用烏龜

烏龜功能由以下設定開啟：

```env
ENABLE_TURTLE_MODULE=true
SYSTEM_PROMPT_FILE=./prompts/assistant.md
KNOWLEDGE_DIR=./knowledge
```

核心版會把 `ENABLE_TURTLE_MODULE` 設為 `false`，並換成通用品牌、通用 System Prompt 與空白知識庫。聊天、RAG、引用、帳號、後台、Usage、權限與 NVIDIA Provider 都是同一套共用程式。

替換 Markdown、品牌與提示詞不需修改程式；但若要把「烏龜 Profile」改成「學生 Profile」或其他結構化領域資料，仍需調整資料表、API 與前端表單。`ModelProvider` 已定義擴充介面，但目前可直接使用的實作只有 NVIDIA Hosted NIM，尚未內建 vLLM。

## 更換烏龜知識

直接新增、修改或刪除 `knowledge/**/*.md`，然後執行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.cli validate-knowledge
..\.venv\Scripts\python.exe -m app.cli sync-knowledge
```

純 Markdown 可以直接索引；YAML frontmatter 用來補充來源、標籤與審閱日期。

內建 12 份文件是用來展示分段、Embedding、檢索與引用流程的專案示範資料，並未經獸醫專業審閱。正式部署前，請由具資格的資料負責人審閱或直接換成組織自己的授權內容。

## NVIDIA 模型與中文 Vision 注意事項

- Chat：[`mistralai/ministral-14b-instruct-2512`](https://build.nvidia.com/mistralai/ministral-14b-instruct-2512)
- Fallback：[`mistralai/mistral-nemotron`](https://build.nvidia.com/mistralai/mistral-nemotron)
- Vision：[`mistralai/ministral-14b-instruct-2512`](https://build.nvidia.com/mistralai/ministral-14b-instruct-2512)
- Embedding：[`nvidia/llama-nemotron-embed-1b-v2`](https://build.nvidia.com/nvidia/llama-nemotron-embed-1b-v2/modelcard)

預設 Ministral 同時支援文字與圖片；NVIDIA 的模型資料列出中文為支援語言，Embedding 模型也列出中文與跨語言檢索能力。Hosted 模型供應狀態可能改變，所有型號都能在 `.env` 更換。正式展示前仍必須使用自己的私人 Key 與實際烏龜照片完成文字、圖片及 Embedding Smoke Test。

## 在伺服器部署

本機快速開始預設只監聽 `127.0.0.1`。公開部署至少要在 `.env` 設定：

```env
APP_ENV=production
APP_ORIGIN=https://assistant.example.org
SESSION_SECRET=獨立產生的長隨機字串
```

在 Caddy、Nginx 或雲端 Load Balancer 後方以單一程序啟動：

```bash
APP_HOST=0.0.0.0 APP_PORT=8000 bash scripts/start.sh
```

Windows Server 可改用：`$env:APP_HOST='0.0.0.0'; $env:APP_PORT='8000'; .\start.cmd`。

反向代理必須提供 HTTPS，`APP_ORIGIN` 必須與瀏覽器實際使用的 Origin 完全一致。請持久化並備份 `backend/data/` 與 `backend/uploads/`。SQLite 適合單機展示；多實例部署應先完成 PostgreSQL 驅動、migration、共享限流與 staging 整合測試。更完整的部署邊界請見[系統架構版 README](https://github.com/richie7p/nvidia-nim-rag-platform#在伺服器部署)。

## 測試

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
npm.cmd audit --audit-level=moderate
```

測試使用 Fake Provider，不會讀取真實 NVIDIA Key。GitHub Actions 會在 `windows-latest`、`ubuntu-latest` 與 `macos-latest` 執行相同測試；macOS/Linux 可把 Python 路徑換成 `../.venv/bin/python`，把 `npm.cmd` 換成 `npm`。

瀏覽器測試使用專案管理的 Chromium，首次執行前須先安裝。測試設定會自動選擇 Windows、macOS 或 Linux 的 `.venv` Python 路徑；使用其他環境時可設定 `E2E_PYTHON`。E2E 會清空伺服器的 `AI_API_KEY`，只驗證註冊、介面與 Profile 流程；AI/RAG 行為由後端 Fake Provider 測試，真實模型須另外驗證。

## 修復紀錄與後續工作

依賴修補、測試範圍及待驗證項目集中在 [技術稽核修復紀錄](docs/AUDIT-FOLLOWUP.md)。CI 包含依賴掃描、型別檢查、單元測試、建置與桌機／手機流程測試。

## 常見問題

- `start.ps1 無法載入`：請在專案根目錄執行 `.\start.cmd`，它只為這次啟動套用 Execution Policy Bypass。
- `.venv was not found`：確認目前位於 clone 下來的 repository 根目錄，再重做 venv 與 pip 安裝。
- 首頁顯示「frontend not built」：在 `frontend/` 執行 `npm ci`、`npm run build`，或重新執行啟動腳本。
- AI 顯示未設定：確認根目錄 `.env` 內有 `AI_API_KEY`，修改後重新啟動。
- 知識庫沒有引用：先以管理員執行 `validate-knowledge` 與 `sync-knowledge`；後者會使用 NVIDIA Embedding 額度。
- 模型停止服務或 404：到 NVIDIA Build 選擇目前可用模型並更新 `.env`；若更換 Embedding 模型，必須重新同步知識庫。
- Port 8000 已被使用：先停止舊服務，或用 `$env:APP_PORT='8010'; .\start.cmd` 改用其他 Port。

## 安全提醒

- `.env`、資料庫、uploads 與 API Key 已排除在 Git 之外。
- API Key 永遠只由 FastAPI 後端呼叫，不會送到 React 瀏覽器。
- 若 Key 曾經公開，請撤銷後重新建立。
- 本工具提供一般飼養資訊，不能取代合格爬蟲類獸醫診斷。

## License

MIT

## 升級既有安裝

更新本版本前，先停止服務並備份資料庫與 uploads。更新程式後，在 `backend/` 執行 `python -m alembic upgrade head`（請使用專案虛擬環境的 Python），完成後再啟動服務。請先執行 migration，再同步知識庫。

本次 migration 會將現存回答的引用轉成來源快照，保留當時的標題、來源與章節，避免知識文件更新後引用消失。升級前已被刪除的引用無法由這次 migration 復原。
