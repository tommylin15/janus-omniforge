# Janus SPEC — 全市場歷史資料種子收錄與 Serving 快取生命週期契約

> **權威宣告**：本規格為補齊個股歷史資料（2 年日頻 OHLCV、3 年單季 EPS、2 年單月營收、KD 線與河流圖基礎數據）之架構與日常運作契約。依據 [`PROJECT_RULES.md`](../PROJECT_RULES.md) §1.7（第三方公開來源核准）與 §1.3（GCP Free Tier 資源守護），本契約明確劃分 Core Iceberg（全量冷儲存）與 PostgreSQL Serving（有界熱快取）的責任邊界，並制定日常自動滾動與淘汰排程。

---

## 1. 背景與問題定義

1. **現況缺口**：
   - 使用者反映個股圖表缺乏足夠歷史資料，導致 2 年日 K 線圖、KD 指標線、營收趨勢圖、本益比河流圖（Valuation River Chart）多數處於缺失或截斷狀態。
   - 官方交易所（TWSE / TPEx / MOPS）對海外機房 IP 存在嚴格速率限制與定時阻擋（Cloud Run / 外網存取頻繁出現 403 / 429 或 Timeout）。
2. **解決途徑**：
   - 採行「**一次性全市場歷史種子收錄（Seed Collection） $\rightarrow$ 轉入 Core Iceberg $\rightarrow$ 投影至 PostgreSQL Serving 快取 $\rightarrow$ 接入日常批次滾動更新與淘汰**」。
   - 資料來源依 [`PROJECT_RULES.md`](../PROJECT_RULES.md) §1.7 採用已核准之公開第三方來源（Yahoo Finance TW API 及網頁端點），具備零 IP 阻擋、免驗證碼、高可用且數據結構標準之特性。

---

## 2. 雙層儲存架構與資料分流

本系統堅持 **「分析倉（Iceberg）與即時讀取庫（PostgreSQL）分工」** 原則：

```mermaid
flowchart TD
    A["第三方來源 (Yahoo Finance TW)<br/>TWSE / TPEx 全市場 1,991 檔"] --> B["種子蒐集腳本 (fetch_2y_history_seed.py)<br/>輕量 gzip JSONL 壓縮傳輸 (< 40MB)"]
    B --> C["Core Iceberg (GCS 冷儲存 / 完整歷史)<br/>100% 全市場 × 2~3 年完整歷史 (永久/受控保存)"]
    C --> D["PostgreSQL Serving 快取 (熱儲存 / 低延遲讀取)<br/>control.stock_serving_recent / market_serving_recent"]
    D --> E["使用者前端 / 視覺端點<br/>K線、KD線、河流圖、單季EPS、營收走勢"]
    
    subgraph PostgreSQL_Free_Tier_Guard["PostgreSQL Free Tier 護欄保護 (e2-micro 1GB RAM / 30GB Disk)"]
        D1["Tier 1 (持股 / 關注 / 高流動性 ~150-200 檔)<br/>保留 2 年 (485~500 交易日) 日頻行情"]
        D2["Tier 2 (全市場其餘 ~1,800 檔)<br/>保留 90~120 天近端日頻行情"]
        D3["低頻基本面 (全市場 1,991 檔)<br/>單季 EPS 12 季 + 單月營收 24 個月 (< 10MB)"]
    end
    D --> D1
    D --> D2
    D --> D3
```

### 2.1 儲存層級職責

| 儲存層級 | 載體 | 資料範圍 | 讀取端 | 職責與特性 |
|---|---|---|---|---|
| **Core 湖倉 (Silver)** | GCS Iceberg (Parquet) | 全市場 1,991 檔 $\times$ 完整 2~3 年歷史 | Ingestion Jobs / 特徵工程 / Mart 分析 | 規範化單一事實來源（Single Source of Truth），成本極低，支援批次計算與歷史重播 |
| **Serving 快取 (Projection)** | PostgreSQL `control.*_serving_recent` | 分級有界快取（Tier 1: 2年；Tier 2: 120天；基本面: 12季/24月） | FastAPI Public Runtime / User App | 極低延遲點查（Point Query），支撐 Flutter 圖表與白話資訊，嚴格防止磁碟膨脹 |

---

## 3. GCP Free Tier 護欄與分級容量管理

為嚴格遵守 GCP Free Tier 限制（`e2-micro`，1GB RAM，30GB 永久磁碟），PostgreSQL **絕不無界堆放全市場數百萬筆歷史日線**，一律實施分級淘汰（Cold/Hot Tiering）：

### 3.1 儲存容量試算表

| 資料類別 | 對象與深度 | 預估總筆數 (Rows) | 預估磁碟空間 | 記憶體快取負擔 | 結論 |
|---|---|---|---|---|---|
| **低頻：單季 EPS** | 全市場 1,991 檔 $\times$ 12 季 | ~23,892 筆 | ~3.5 MB | 輕微 (< 5MB) | **全量進 Serving 快取** |
| **低頻：單月營收** | 全市場 1,991 檔 $\times$ 24 個月 | ~47,784 筆 | ~6.0 MB | 輕微 (< 8MB) | **全量進 Serving 快取** |
| **高頻：Tier 1 日線** | 持股 / 關注 / 前 150 檔 $\times$ 2 年 (500日) | ~75,000~100,000 筆 | ~25.0 MB | 中等 (~20MB) | **保留 2 年完整走勢與河流圖** |
| **高頻：Tier 2 日線** | 其餘 ~1,800 檔 $\times$ 90~120 天 | ~160,000~210,000 筆 | ~45.0 MB | 中等 (~30MB) | **保留近端日線供 KD/選股** |
| **合計總量** | **全系統 Serving 快取** | **約 250,000 ~ 380,000 筆** | **約 80 ~ 95 MB** | **小於 70MB** | **安全低於 30GB 限制 (< 0.3%)** |

### 3.2 使用者「觀察股與持股」隨時變化的動態處置機制

針對使用者在日常使用中「隨時加入觀察股、新增買進持股、移除觀察股、清空賣出持股」的動態行為，系統設計了雙重保障機制，兼顧**操作即時性**與**資料庫防震盪**：

```mermaid
sequenceDiagram
    autonumber
    actor User as 使用者 (User App)
    participant API as FastAPI / Private API
    participant PG_Serving as PostgreSQL Serving 快取
    participant Demand as 需求佇列 (Sync Demand)
    participant Iceberg as Core Iceberg (完整歷史冷儲存)

    Note over User, Iceberg: 情境 A：使用者隨時「加入觀察股」或「新增買進持股」
    User->>API: 點擊加入觀察清單 / 記錄買進成交
    API->>API: 寫入 private.watchlist 或 private.current_positions
    API->>Demand: 觸發 control.sync_stock_supplement_demand() (去識別化)
    User->>API: 立即點開該個股詳情頁面
    API->>PG_Serving: 查詢該股資料
    PG_Serving-->>User: 【零延遲響應】立即顯示 Tier 2 常駐 120天日線、KD線、12季EPS、24月營收 (完全不空白)
    Note over Demand, PG_Serving: 背景非同步自動升格 (Tier 2 → Tier 1)
    Demand->>Iceberg: 讀取該股其餘 2 年歷史日線 (第 121 ~ 500 天)
    Iceberg->>PG_Serving: 補齊寫入 control.stock_serving_recent
    Note over User, PG_Serving: 前端自動或下次進入即可無縫展開完整 2 年線圖與估值河流圖

    Note over User, Iceberg: 情境 B：使用者隨時「移除觀察股」或「賣出持股清空」
    User->>API: 點擊取消關注 / 記錄賣出庫存歸零
    API->>Demand: 重新計算去識別化活躍聯集 (active_symbols)
    Demand->>Demand: 標記該股進入 30 天緩衝冷卻期 (Grace Period)，不立即刪除
    Note over PG_Serving: 【防震盪保護】避免誤按取消或短期重新加入導致頻繁重複搬移資料
    Note over PG_Serving: 超過 30 天且已非任何持股/觀察股，週六 02:00 維護排程自動修剪回 120 天 (降格回 Tier 2)
    Note over Iceberg: Core Iceberg 始終保留該股完整歷史，未來再度加入可秒級無損還原
```

#### 動態處置三大原則：
1. **即時體驗不等待（Zero-Blank UX）**：
   - 由於全市場 1,991 檔股票在 Serving 快取中**已經常駐 120 天日線、24 個月單月營收與 12 季單季 EPS**。
   - 使用者在盤中或任何時間加入新觀察股或持股時，點開個股詳情頁面，走勢圖與財務資訊**當下就具備可用資料**，絕不會因為正在排程補數而出現空白或卡頓。
2. **背景升格不卡鎖（Tier 2 $\rightarrow$ Tier 1 Promotion）**：
   - 使用者操作觸發 `control.sync_stock_supplement_demand()`，系統自動將該股標記為 Tier 1 需求。
   - 背景任務立即從 Core Iceberg 提取剩餘的 2 年歷史日線（約 380 筆）投影至 `control.stock_serving_recent`。
   - 補齊完成後，完整的 2 年日線圖與本益比/淨值比河流圖自動連通，全程在背景完成，不鎖住使用者操作。
3. **優雅降格與 30 天防震盪緩衝（Grace Period & De-escalation）**：
   - 當使用者移除關注或出清股票時，系統**絕對不立即粗暴刪除資料**。
   - 系統給予 **30 天緩衝冷卻期**。若使用者在 30 天內再度關注或買回，完全不需要重新搬移資料。
   - 只有在滿 30 天且確認不在任何活躍持股或觀察清單內，才由週六 02:00 例行維護作業將其日線修剪回 120 天（降回 Tier 2）。
   - **底層數據零損失**：Core Iceberg 永遠保有完整歷史，隨時可按需重新投影。

---

## 4. 日常正常運作與滾動淘汰排程（Lifecycle Policy）

資料生命週期不能僅限於「首次種子匯入」，必須在日常運作中全自動維護、滾動更新並修剪過期快照：

```mermaid
flowchart LR
    subgraph Daily_1830["每日 18:30 EOD 批次"]
        D_Fetch["抓取今日 OHLCV"] --> D_Iceberg["Append 至 Core Iceberg"]
        D_Iceberg --> D_Tier["計算 Tier-1 / Tier-2 清單"]
        D_Tier --> D_Upsert["Upsert 至 stock_serving_recent"]
        D_Upsert --> D_Prune["修剪過期日線<br/>(Tier-1 > 750d / Tier-2 > 120d)"]
    end

    subgraph Monthly_10th["每月 10 日 21:00 營收批次"]
        M_Fetch["抓取上月營收"] --> M_Iceberg["Append 至 Core Iceberg"]
        M_Iceberg --> M_Upsert["Upsert 至 market_serving_recent"]
        M_Upsert --> M_Prune["修剪超過 24 個月前營收"]
    end

    subgraph Quarterly["每季申報截止日 財報批次"]
        Q_Fetch["抓取最新單季 EPS / BPS"] --> Q_Iceberg["Append 至 Core Iceberg"]
        Q_Iceberg --> Q_Upsert["Upsert 至 market_serving_recent"]
        Q_Upsert --> Q_Prune["修剪超過 12 季前 EPS"]
    end

    subgraph Weekly_Sat["每週六 02:00 DB 維護"]
        W_Sweep["清理孤兒與超期 Serving 快取"] --> W_Vacuum["VACUUM ANALYZE<br/>釋放 dead tuples 與整理 Index"]
    end
```

### 4.1 批次執行時間點與淘汰規則

1. **每日 EOD 行情批次（交易日 18:30 Asia/Taipei）**：
   - **觸發器**：Cloud Scheduler $\rightarrow$ `janus-ingestion-core`。
   - **動作**：
     1. 收錄當日上市櫃個股收盤價、成交量、高低價。
     2. 寫入 Core Iceberg `warehouse/core/ohlcv`。
     3. 刷新 `control.stock_serving_recent` 投影。
     4. **淘汰修剪（Prune）**：
        - 對屬於 **Tier 1** 的股票：執行 `DELETE FROM control.stock_serving_recent WHERE dataset_id = 'ohlcv' AND symbol = :sym AND sort_at < NOW() - INTERVAL '750 days'`（保留 2 年餘裕）。
        - 對屬於 **Tier 2** 的股票：執行 `DELETE FROM control.stock_serving_recent WHERE dataset_id = 'ohlcv' AND symbol = :sym AND sort_at < NOW() - INTERVAL '120 days'`。
2. **每月營收申報批次（每月 10 日 21:00 Asia/Taipei）**：
   - **觸發器**：Cloud Scheduler 於台灣法規營收公告截止（每月 10 日）後啟動。
   - **動作**：
     1. 收錄全市場上月營業收入、MoM、YoY。
     2. 寫入 Core Iceberg `warehouse/core/financials`。
     3. 投影至 `control.market_serving_recent`。
     4. **淘汰修剪（Prune）**：
        - 執行 `DELETE FROM control.market_serving_recent WHERE dataset_id = 'financials' AND payload_json->>'metric' = 'monthly_revenue' AND sort_at < NOW() - INTERVAL '25 months'`（維持 24 個月滑動窗口）。
3. **每季財報申報批次（每年 3/31、5/15、8/14、11/14 22:00 Asia/Taipei）**：
   - **觸發器**：Cloud Scheduler 於法定財報公告日啟動。
   - **動作**：
     1. 收錄最新單季 EPS 與每股淨值（BPS）。
     2. 寫入 Core Iceberg。
     3. 投影至 `control.market_serving_recent`。
     4. **淘汰修剪（Prune）**：
        - 執行 `DELETE FROM control.market_serving_recent WHERE dataset_id = 'financials' AND payload_json->>'metric' = 'eps_single_quarter' AND sort_at < NOW() - INTERVAL '40 months'`（維持 12 季滑動窗口）。
4. **週末例行維護與空間回收（每週六 02:00 Asia/Taipei）**：
   - **觸發器**：現有 PostgreSQL VM 定時 cron 或 Scheduler 維護任務。
   - **動作**：
     1. 執行孤兒檢查與兜底清理。
     2. 執行 `VACUUM ANALYZE control.stock_serving_recent, control.market_serving_recent;`。
     3. 回收過期索引與 dead tuples 空間，防止 PostgreSQL 磁碟產生碎片膨脹。

---

## 5. 資料傳輸與檔案格式規範

1. **避免 binary dependency 與 exec mount 限制**：
   - 種子檔案採用 Python 內建標準庫 `gzip` 與 `json`，產出 `.jsonl.gz` 壓縮檔。
   - 完全不依賴本機 C 編譯、Rust 編譯或 `noexec` 掛載點問題（如 `pyarrow` 在受限使用者目錄的載入限制）。
   - 全市場 1,991 檔歷史日線（約 96 萬筆）壓縮後總容量小於 **35 MB**，極度輕量便於上傳與搬移。
2. **存放目錄規範**：
   - 本機產出：`data/seed/*.jsonl.gz`
   - GCS 備份與 Stage 匯入：`gs://{PROJECT_ID}-stage/seed_data/`
   - Google Drive 正式留存：`janusChatGPT/seed_data/`
3. **資料表 Schema 對齊**：
   - 日頻行情：`control.stock_serving_recent` (`dataset_id='ohlcv'`)
   - 單季 EPS：`control.market_serving_recent` (`dataset_id='financials'`, `payload_json->>'metric'='eps_single_quarter'`)
   - 單月營收：`control.market_serving_recent` (`dataset_id='financials'`, `payload_json->>'metric'='monthly_revenue'`)
