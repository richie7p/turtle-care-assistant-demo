# NVIDIA 真實 API 測試

## 加強測試與修正（2026-10-04）

再次檢查後，新增 19 項 provider 與 API 回歸案例，完整後端測試共 73 項通過。已修正：

- 串流在結束標記前斷線或達到輸出長度上限時，保留部分回答並標示中斷，不再當成完成，也不會重播部分內容。
- 錯誤／空白模型回應轉成可處理的服務錯誤。
- Embedding 的筆數、索引、維度與有限非零數值均驗證；無效資料會讓知識庫查詢顯示不可用，避免回傳無依據引用或直接崩潰。
- 等待中的 Embedding 請求有 30 次輪詢上限；零 token 用量也會正確保留。

使用修正後程式連續執行三輪下列四項真實 NVIDIA 流程，每輪 4/4，共 12/12 通過。包含 Embedding、引用與對話儲存、圖片辨識和真實模型備援；沒有失敗後只挑成功結果計分。API 異常情境則使用可重現的模擬回應測試。

以下表格保留前一輪的歷史結果；三轮重測未使用真實患者、真實醫療文件或既有使用者資料。

2026-10-04，Windows 本機，使用授權金鑰、合成資料與真實 NVIDIA hosted API。最後一輪 4 項流程檢查通過。小樣本不代表醫療／獸醫準確率、穩定性、成本或 production 驗收；自動 CI 仍使用 Fake Provider，不消耗真實額度。

## 重跑

完成 README 的依賴安裝，將 `AI_API_KEY` 放在未追蹤的 `.env` 或程序環境，再執行：

```powershell
python tools/smoke_nvidia.py --report live-nvidia.json
```

從 `backend/` 執行；此工具依賴 `requirements-dev.txt` 中的 TestClient。測試建立暫存 SQLite、合成知識文件與圖片，不使用既有 DB／uploads。來源向量與查詢使用真實 Embedding。要測烏龜模組請依 `.env.example` 啟用 `ENABLE_TURTLE_MODULE=true`。

預設文字／圖片／Embedding／備援模型已更新；既有 `.env` 的舊模型值不會被自動覆寫。請更新後重跑 `python -m app.cli sync-knowledge` 重建舊向量。

## 最後一輪實測

| 檢查 | 結果 | 當次耗時 |
| --- | --- | --- |
| `real_embedding_index` | 通過 | 1024 ms |
| `real_streaming_rag_and_persistence` | 通過 | 3798 ms |
| `real_image_upload_and_streaming_vision` | 通過 | 1821 ms |
| `real_streaming_fallback` | 通過 | 425 ms |

耗時為單次流程（可能含多個 NVIDIA 請求），不是統計延遲或 SLA。

## 首次失敗及限制

原 NIM RAG／烏龜照護文字及 Embedding 模型在本次金鑰與端點上回傳 model_unavailable；這不代表已確認全域退役。更新後的文字、vision、Embedding 與 fallback 均經真實呼叫。

第一輪 NIM RAG 圖片串流沒有回答內容，且產生的標題包含多行與程式碼。已新增無內容且尚未輸出時的一次重試，以及標題第一行清理／18 字上限；54 項後端測試與修正後真實流程通過。

備援測試以不存在的合成主模型觸發實際 NVIDIA 錯誤，再由真實備援模型回答。沒有在圖片失敗時將圖片送往文字備援。

不代表完整實機部署或雲端 production 驗證；知識文件仍需資料負責人／藥師／獸醫審閱。金鑰未進入 repository、報告或 GitHub Actions；真實測試須手動啟動，會消耗帳戶可用額度。
