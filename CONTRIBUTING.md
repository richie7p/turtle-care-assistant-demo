# Contributing

感謝協助改善 NVIDIA NIM RAG Platform 與示範 preset。

1. 不要提交 `.env`、API Key、資料庫、uploads、logs 或真實使用者資料。
2. 功能修改需補上對應 Pytest 或 Vitest；介面流程修改需確認 Desktop 與 Mobile E2E。
3. 修改共用核心時，同時測試 `core` 與 `turtle` 兩個匯出版。
4. 知識文件應附上可核對的來源與審閱日期；不要提交受版權限制的完整第三方文章。
5. Pull Request 請說明動機、行為變更、測試結果與是否影響 migration 或環境變數。

本機驗證：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

