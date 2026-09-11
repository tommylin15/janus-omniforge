# Janus Admin `/admin/stocks` 使用指南

適用環境：Janus dev Admin UI  
頁面：`https://janus-web-2oo7qbkd5q-uc.a.run.app/admin/stocks`

## 1. 登入與基本原則

1. 開啟頁面後，以已加入 allowlist 的 Google 帳號登入。
2. 頁首顯示「控制面服務正常」後再開始操作。
3. 本頁的長任務只會建立 queued execution，不代表資料收集或分析已完成。
4. 會改變資料的操作應先確認股票代號、設定 ID、選取數量與生效時間。
5. 操作完成後，到「最近執行」確認狀態；`queued`、`running`、`retrying` 都不是完成。

## 2. 頁面區域

| 區域 | 用途 |
|---|---|
| 股票管理 | 搜尋、新增、編輯、啟停、查看 Core 資料狀態及刪除股票 |
| 批次操作 | 對已選股票建立 Collection execution；第一階段不使用 Analysis |
| 最近執行 | 顯示最近 50 筆 persisted execution 與工作明細 |
| 資料源健康 | 顯示已持久化的 telemetry，不會在開頁時呼叫上游來源 |
| 核心 50 名單 | 建立有生效時間、操作者及理由的名單版本 |
| 排程與保存設定 | 保存排程及 Stage retention 設定版本 |
| 資料源設定 | 唯讀顯示 collection config 與授權狀態 |

## 3. 股票查詢與選取

### 搜尋與篩選

1. 在搜尋框輸入股票代號或名稱的一部分。
2. 可選擇「全部狀態」、「已啟用」或「已停用」。
3. 按「搜尋」。每頁固定顯示 10 筆。
4. 使用「上一頁」與「下一頁」切換頁面。

變更啟用狀態篩選時會自動重新查詢，不必再按搜尋。

### 選取股票

- 勾選每列左側 checkbox，可選取個別股票。
- 勾選表頭 checkbox，可選取或取消本頁全部股票。
- 選取會跨頁保留，但重新載入整個網頁後會清空。
- 按「清除選取」可一次移除所有選取。
- 頁面上方與批次工具列都會顯示目前選取數量。

搜尋或篩選不會自動清除原本跨頁選取；建立批次前務必再次核對「已選股票」數量。

## 4. 新增與編輯股票

### 新增

1. 按「新增股票」。
2. 輸入英數字股票代號與名稱。
3. 選擇市場：`TWSE` 或 `TPEX`。
4. 選擇上市狀態：
   - `listed`：上市／上櫃中
   - `suspended`：暫停交易
   - `delisted`：終止上市／上櫃
   - `unknown`：尚未分類
5. 決定是否啟用。
6. 按「儲存」。

### 編輯

1. 在股票列按「編輯」。
2. 股票代號不可修改；可調整名稱、市場、上市狀態與啟用狀態。
3. 按「儲存」，等待「股票資料已儲存」提示。

目前 dialog 右上角「×」有已知取消問題。需要放棄變更時請按 `Esc`，不要使用「×」。

## 5. 每列操作

| 按鈕 | 效果 | 成功判斷 |
|---|---|---|
| 編輯 | 開啟股票編輯 dialog | 儲存後出現成功提示，列表內容更新 |
| 啟用／停用 | 更新 public／collection 可使用狀態 | 提示顯示已啟用或已停用，狀態 badge 更新 |
| 資料狀態 | 讀取該股票的 Core summary | 顯示資料集筆數、最新日期、null profile 等摘要 |
| 刪除 | 刪除未被控制面引用的股票 | 確認後提示已刪除，股票從列表消失 |

停用股票不會被 enabled-only collection 選取，也不應出現在 public 股票搜尋。

刪除前會檢查 collection config、execution、market、report、fundamental 五類引用；任一引用數量非零時 API 會拒絕刪除，Admin 會顯示各類數量與解除引用原因。

## 6. 建立 Collection execution

1. 選取一檔以上股票。
2. 在「設定 ID」輸入已存在且允許相應 trigger 的 collection config ID，例如 `ohlcv`。
3. 按「加入 Collection」建立資料收集 execution。
4. 記下提示中的 execution ID。
5. 到「最近執行」確認新項目狀態。

Collection 命令寫入 persisted queue 後由既有 consumer 處理；成功取得 execution ID 仍只代表成功排隊，必須在「最近執行」確認 terminal status。第一階段正式介面會將 Analysis hidden／disabled；若舊 revision 仍顯示「加入 Analysis」，不得使用，因 Mart persisted consumer 尚未完成。

## 7. 查看最近執行

- 頁面載入最近 50 筆 persisted execution。
- 「進行中」統計包含 `queued`、`running`、`retrying`。
- 按區塊右上方「重新整理」只更新 execution 列表。
- 按每列「查看」，才會讀取 execution items 與安全化訊息。
- 在明細 dialog 按「×」可關閉。

常見狀態：

| 狀態 | 意義 |
|---|---|
| `queued` | 已排隊，尚未由 worker claim |
| `running` | worker 正在執行 |
| `retrying` | 先前嘗試失敗，等待重試 |
| `succeeded` | 已成功完成 |
| `partial` | 部分資料完成，需查看工作項目 |
| `failed` | 執行失敗，需查看安全化錯誤與 logs |

## 8. 核心 50 名單

1. 輸入股票代號，以逗號、空白或換行分隔；重複代號會自動去重。
2. 名單最多 50 檔，且代號必須已存在於股票主檔。
3. 設定生效時間。畫面使用瀏覽器本地時間，送出時轉為 ISO UTC。
4. 填寫操作者與變更理由。
5. 按「儲存不可變更版本」。

此操作會建立具時間效力的新版本。送出前應特別檢查生效時間，避免意外提前或延後切換名單。

## 9. 排程與保存設定

1. 設定排程時間與是否啟用排程。
2. 設定 Stage 保留天數（1–3650）及是否啟用 cleanup。
3. 填寫操作者。
4. 按「儲存設定」。

設定使用 optimistic version，若其他人已更新，系統會要求重新載入後再儲存。排程與 retention 是兩筆依序保存的設定，並非單一原子交易。

現行 dev 只確認設定會寫入 control DB 並留下 audit；尚無程式讀取這兩個設定去更新 Cloud Scheduler 或實際 cleanup 流程。需要調整真正的排程或清理行為時，仍須依 deployment runbook 操作。

## 10. 重新整理與唯讀資訊

- 頁首「重新整理」會重新載入股票、execution、資料源健康、來源設定、核心名單及排程／保存設定。
- 「資料源健康」只讀 persisted telemetry；它不會立即測試 TWSE、TPEx、MOPS 或 FinMind。
- 「資料源設定」目前實作仍為唯讀；正式規格只規劃管理已核准來源的 cadence、coverage tier 與 authorization status。
- `candidate` 或 `blocked` 資料源只保留設定狀態，不提供審查或啟用控制。

## 11. 已知限制

- 目前沒有可見的登出按鈕；session 到期後會要求重新登入。
- 股票 dialog 的「×」會進入 submit handler，取消時請使用 `Esc`。
- execution 明細只能按「查看」開啟，尚未支援規格要求的整列 click。
- dialog 關閉後不保證恢復到原本 opener 的鍵盤焦點。
- Collection consumer 已存在；Analysis／Mart persisted consumer 尚未完成，舊 revision 的 Analysis 按鈕不得使用。
- 排程與 retention 設定目前只持久化，尚未驅動 Cloud Scheduler／cleanup runtime。
