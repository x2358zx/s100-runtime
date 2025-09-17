# S100 Log Analytics Stack

使用 Docker Compose 佈署的完整架構：FastAPI + MySQL + phpMyAdmin + Streamlit。
- 解析並匯入 `YYYYMM_total_run_time.txt` 與歷史 `S100_test_log/` 的資料
- 自動去重 / 容錯，產生 `runs` 表
- 每日 23:00 自動匯入當月檔 + 計算每日稼動率（以合併時段方式避免重複膨脹）
- Streamlit 儀表板提供互動視覺化與報表下載

## 快速開始

1. 建立 `.env`（可參考 `.env.example` 並修改主機路徑與密碼）：
   ```
   cp .env.example .env
   # 編輯 .env，設定 LOG_ROOT_S100_1、LOG_ROOT_S100_2 指向 Ubuntu 主機上的分享資料夾
   ```

2. 啟動：
   ```
   docker compose up -d --build
   ```

3. 服務位置：
   - API: `http://<host>:8000/docs`
   - phpMyAdmin: `http://<host>:8081`
   - Streamlit: `http://<host>:8501`

4. 匯入資料（選擇其一）：
   - 立刻匯入當月：
     ```bash
     curl -X POST http://<host>:8000/ingest/current
     ```
   - 一鍵重建所有歷史月份（會掃描 `<ROOT>/S100_test_log/` 內所有 `*_total_run_time.txt`）：
     ```bash
     curl -X POST http://<host>:8000/ingest/historical
     ```

## 稼動率定義
**每日稼動率** = 將該日所有測試時段做「區間合併」後的總秒數 / 24 小時。
- 若同時段有多筆（例如 ENG 測試重複紀錄），合併後只計算一次，避免膨脹。
- 亦可在 Streamlit 以設備/專案/日期篩選觀察。

## 去重與資料防堵機制
1. **雜湊去重**：以 `equipment|StTime|SpTime|Project|LogName` 產生 SHA1，原始表 `raw_logs` 具有唯一鍵避免完全重複。
2. **容錯合併**：同專案/樣品/測項在時間上互相重疊者視為同一群；保留 **較長** 的區間與秒數（處理「同一筆不同時間」）。
3. **一致性檢查**：若 `| (Sp-St) - TotalTime | > 1s`，記錄 `conflict_reason=time_mismatch` 以便審視。
4. **ENG 標記**：偵測 `ENG-<tag>-` 前綴，記為 `eng_flag/eng_tag`；正式資料 `eng_flag=0`。
5. **欄位缺漏**：舊 LOG 不含 `user/prgver/codever` 則以 `NULL` 儲存，相容新舊格式。
6. **Site/配件/分類**：從 `LogName` 以底線分割取得；若無法符合模式則填 `NULL`。

> 備註：`Project=客戶_ProjectCode`、`LogName` 例如 `S0004_4P7V_C6_25C_TT_S12COB_s2`；ENG 例：`ENG-8-S0001_3P5V-RUN4_C8_25C_TT_S12A24_s2`。

## 建議
- 若要改以「計畫排程時段」計算理論稼動率，可在 API 加入班表設定，讓分母改為排程總時數（非 24 小時）。
- 若要即時監控，可將排程頻率由每日改為每小時，或加入 inotify/檔案指紋以增量讀取。
- 若需與現有系統整合，可在 API 增加 JWT 或反向代理保護、或新增 Grafana/Redash 連接本 DB。

## 資料表
- `raw_logs`：原始逐行資料（含解析欄位與雜湊）。
- `runs`：去重後的測試區間（供分析/視覺化）。
- `metrics_daily`：每日設備稼動率。

## 匯出
- REST：`/reports/records.csv`、`/reports/records.xlsx`（可加 query 篩選）。
- Streamlit：頁面提供 CSV 下載按鈕。

## 版權
MIT
