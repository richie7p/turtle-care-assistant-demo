# 🐢 烏龜飼養小助手 — NVIDIA NIM RAG 實力示範

這是 `NVIDIA NIM RAG Platform` 的完整領域示範版，用烏龜飼養呈現同一套架構如何結合 Profile、私有圖片、Vision、RAG、醫療安全規則與管理後台。

若要改造成學校、公司或其他主題的助理，請從不含領域資料的 [NVIDIA NIM RAG Platform 系統架構版](https://github.com/richie7p/nvidia-nim-rag-platform) 開始。

下載者必須自行申請並填入 NVIDIA NIM API Key；repository 不包含作者的 Key、帳號、資料庫或測試密碼。

## 示範內容

- 多隻烏龜 Profile：物種、水龜／陸龜、體型、環境、UVB、加熱與飲食
- 對話指定龜龜，自動把 Profile 注入 AI Context
- JPEG／PNG／WebP 圖片分析、EXIF 移除、尺寸與數量限制
- 12 份繁體中文示範知識：水龜、陸龜、UVB、水質、溫濕度、過濾、曬背與飲食
- 回答引用原始資料，沒有合格 RAG 結果時不製造來源
- 照片只能描述可觀察現象，不會僅憑圖片確診
- 出血、重傷、呼吸異常、長期拒食等情況才自然建議爬蟲類獸醫
- 使用者／對話／龜龜／附件完整權限隔離
- 後台營運總覽、AI 紀錄、知識同步、NIM 健康檢查與管理稽核

## 快速開始

需求：Python 3.11、Node.js 22 以上。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Set-Location frontend
npm.cmd install
Set-Location ..
Copy-Item .env.example .env
```

開啟 `.env`：

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

開啟 <http://127.0.0.1:8000>。本專案不提供預設帳密。

## 如何證明它不只適用烏龜

烏龜功能由以下設定開啟：

```env
ENABLE_TURTLE_MODULE=true
SYSTEM_PROMPT_FILE=./prompts/assistant.md
KNOWLEDGE_DIR=./knowledge
```

核心版會把 `ENABLE_TURTLE_MODULE` 設為 `false`，並換成通用品牌、通用 System Prompt 與空白知識庫。聊天、RAG、引用、帳號、後台、Usage、權限與 NVIDIA Provider 都是同一套共用程式。

## 更換烏龜知識

直接新增、修改或刪除 `knowledge/**/*.md`，然後執行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.cli validate-knowledge
..\.venv\Scripts\python.exe -m app.cli sync-knowledge
```

純 Markdown 可以直接索引；YAML frontmatter 用來補充來源、標籤與審閱日期。

## 測試

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

## 安全提醒

- `.env`、資料庫、uploads 與 API Key 已排除在 Git 之外。
- API Key 永遠只由 FastAPI 後端呼叫，不會送到 React 瀏覽器。
- 若 Key 曾經公開，請撤銷後重新建立。
- 本工具提供一般飼養資訊，不能取代合格爬蟲類獸醫診斷。

## License

MIT
