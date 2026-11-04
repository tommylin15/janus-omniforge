# Janus Shioaji 專屬報價轉發服務規格（asia-east1）

## 1. 背景與設計目的

台股盤中交易需要秒級、零延遲的真實即時行情（Tick、五檔、成交量與昨收價）。然而本機分析環境與主要計算節點常位於 Google Cloud 美國機房或受限出站防火牆環境，直接對台灣永豐金證券（HiNet IP `210.59.255.161`）或證券交易所 TWSE MIS 請求時會遭遇連線逾時（Egress Timeout）或地域性封鎖（Geo-blocking）。

為此，在 GCP 台灣機房（`asia-east1`）部署輕量且專屬的 **`shioaji-quote-proxy`** 服務，做為股市高頻即時行情的專屬轉發橋樑。

---

## 2. 架構與職責邊界

- **專案與位置**：`gen-lang-client-0593591102`，區域 `asia-east1`。
- **程式碼目錄**：[`services/shioaji_quote_proxy/`](file:///home/tommylin15_gmail_com/.gemini/antigravity-cli/scratch/janus-omniforge/services/shioaji_quote_proxy/)
- **服務名稱**：`shioaji-quote-proxy` (Cloud Run)
- **憑證與機密原則**：
  - 重用既有 GCP Secret Manager 的 `janus-runtime-bundle:latest`，絕不重複建立冗餘密鑰或在程式庫中明文存放憑證。
  - 容器於啟動時由環境變數讀取 JSON Bundle，自動提取 `shioaji_api_key`、`shioaji_secret_key` 等憑證。
- **雙軌行情備援設計**：
  1. **主軌（Shioaji 原生）**：容器連線永豐金證券 API，下載股票合約快取，透過 `api.snapshots()` 取得高頻即時行情。
  2. **備援軌（在地 TWSE MIS）**：若遇非交易時段、合約未及下載或券商伺服器維護，由位於台灣的容器直接向 `mis.twse.com.tw` 發送請求並解析五檔與成交數據，確保轉發 API 100% 可用。

---

## 3. 安全與身份驗證

- **訪問控制**：Cloud Run 配置 `--no-allow-unauthenticated`，禁止公開存取。
- **Caller 身份授權（IAM Invoker）**：
  - `postgres-vm@gen-lang-client-0593591102.iam.gserviceaccount.com`（本機專用分析 VM）
  - `janus-user-api@gen-lang-client-0593591102.iam.gserviceaccount.com`（Janus 核心 API）
- **呼叫機制**：調用端透過 GCP Metadata Server (`http://metadata.google.internal/...`) 動態簽發 Audience 指定的 OpenID Connect (OIDC) ID Token，透過 `Authorization: Bearer <ID_TOKEN>` 進行認證。

---

## 4. API 端點規格

### `GET /health`
檢查服務狀態、所在區域與 Shioaji 連線狀態。
```json
{
  "status": "ok",
  "service": "janus-shioaji-quote-proxy",
  "region": "asia-east1",
  "timestamp": "2026-11-04T11:40:00+08:00",
  "shioaji": {
    "logged_in": true,
    "contracts_fetched": true,
    "has_credentials": true,
    "login_error": null
  }
}
```

### `GET /quotes?symbols=2382,2327,5876`
批量查詢股票即時快照，回傳現價、昨收、漲跌幅、五檔買賣價量與資料來源標記。

### `GET /quote/{symbol}`
單檔個股查詢。

---

## 5. 自動化部署與持續整合

- 工作流程檔：[`.github/workflows/deploy-shioaji-quote-proxy.yml`](file:///home/tommylin15_gmail_com/.gemini/antigravity-cli/scratch/janus-omniforge/.github/workflows/deploy-shioaji-quote-proxy.yml)
- 觸發條件：`services/shioaji_quote_proxy/**` 異動時自動觸發。
- 驗收項目：單元測試、Cloud Build 容器構建、Cloud Run 部署、IAM 授權綁定與 OIDC Smoke Test。

---

## 6. 強制 Shioaji Simulation 模式（2026-11-04 使用者決策）

本規範適用於 `shioaji-quote-proxy` 現有服務及後續 Janus 全盤中行情統一接線、多人共用、按需更新的所有實作，優先於其他未明列 Simulation 模式的說明。

1. Shioaji Client **必須明確初始化為 `sj.Shioaji(simulation=True)`**。不可依賴套件預設值，不得透過環境變數、fallback、重新登入或其他程式碼路徑將其改成 `simulation=False`；無法確認模式時 fail closed，不使用未確認模式的 Shioaji 連線。
2. Proxy 僅可使用行情讀取／訂閱 API（例如 `quote.subscribe`、`quote.unsubscribe`、`ticks`、`kbars`、`snapshots`），**禁止實作或呼叫任何下單、改單、取消單、帳戶交易功能**。Simulation 不等於 API 不存在下單能力，仍須保留程式級禁止交易邊界。
3. 必須讓私有 health／診斷結果可讀回 `simulation=true` 的實際 Client 初始化模式；啟動、重連、重啟及部署後驗收都核對它，不能僅以文件或設定宣稱已生效。
4. 與盤中按需架構配合：頁面前景有效時每 60 秒 revalidate，關閉或背景停止；跨使用者／API instance 依 shared quote cache + distributed singleflight/lease 去重；不可因多人進入頁面重複建立 Shioaji login／訂閱。不得新增每分鐘 Cloud Scheduler／Job。行情模式及價格來源須分開標記，模擬交易模式不等於行情價格可虛構。
5. Shioaji 官方提醒 `snapshots()` 不得盤中反覆輪詢當即時 feed，正式每分鐘 UI 讀取應建立在受控的 `quote.subscribe()` 訂閱快取上；只有取得合法實際行情時才能呈現，缺值保留 missing／stale，不能拿昨收假冒當日成交。

**實作／驗收狀態：**本節是使用者核准的強制設計要求，僅回寫 SPEC。現有 `services/shioaji_quote_proxy/main.py` 的 `sj.Shioaji()` 尚未改為明確 `simulation=True`；不能因文檔更新宣稱目前 Runtime 已符合。本節修改不觸發部署；後續工程需補程式、測試、CI、Cloud Run Live 讀回才可關閉。

參考：[Shioaji 官方 Simulation Mode](https://sinotrade.github.io/tutor/simulation/)；[官方 Snapshot 使用限制](https://sinotrade.github.io/zh/tutor/market_data/snapshot/)。

## 7. 盤中行情統一按需讀取與多人去重（2026-11-04）

### 正式資料路徑

- Today／Watchlist／Holdings／Stock Detail 每分鐘僅在頁面可見且 App 在前景時向 Janus API revalidate；無每分鐘 Scheduler、Job 或全市場掃描。
- Janus API `ShioajiQuotes` 使用 Cloud Run IAM/OIDC 呼叫私有 `shioaji-quote-proxy`。Proxy 禁止正式交易 Client，固定 `simulation=True`；以 Shioaji `Quote` 訂閱回調資料為主（`TAIEX` 對應 `IX0001`），沒有定時 `snapshots()`。
- 同一 Proxy Cloud Run 暫採 `max-instances=1`，避免同一券商帳號出現多個連線管理者。每檔在實例內只有一個訂閱，無活動需求（130 秒內未續用）於下一次需求請求清理；若實例無請求，Cloud Run scale-to-zero 最終結束連線。此設計**不保證無請求期間仍能收滿全天分鐘點**。
- Janus API 跨實例以 PostgreSQL session advisory `pg_try_advisory_lock` 實施 singleflight：同時間最多一筆上游刷新，後來者先讀 last-success，不建立重疊查價任務；拿到鎖後重新以 persistent `received_at` 評估 60 秒 TTL。
- Proxy 統一容納既有按需 MIS 備援；缺 Shioaji 推播時以有界 MIS 查詢補回，MIS 不把昨收補成當日成交。嚴格校驗股票代號、交易所（TSE／OTC）、報價時間與正值，回傳 `shioaji` 或 `twse_mis` 真實 source；來源失敗只回 stale／missing。Proxy 的服務回應不代表該 symbol 一定取得報價。
- `control.operational_last_quotes` 為 last-success Operational 快取，不能取代正式 EOD。每個已取得的 TAIEX 觀測每分鐘最多保存一個真實點於 `control.operational_index_minutes`（migration 073），只供「今日盤中」分時圖；缺口不補，正式近 5／20／30 日線仍由 canonical EOD 供應。
- 現有「非盤中手動更新」仍可按需查詢最後有效觀測；非盤中一般 GET 不自動喚醒上游，缺交易時必須標 stale。單純 revalidate 不得重算四模型或年度已實現損益。

### 已知限制及正式驗收

1. Cloud Run `min-instances=0` 且請求期間才有 CPU 時，訂閱 callback 僅在有請求 CPU 的窗口能可靠處理；不能保證完全連續逐筆 push。要提供長時間完整分鐘軌跡需要獨立評估串流常駐及其費用，不得本輪私自新增付費常駐資源。
2. 單實例 `max-instances=1` 配合 Proxy 進程內訂閱快取；倘若日後改成多實例，必須先移轉為真正跨 Proxy 實例的訂閱 owner／lease，否則不能直接加實例數。
3. 訂閱上限保守 150，Proxy 單次請求最多 30 檔；Janus 分批查詢，跨使用者去重仍受 API 共享鎖及 persistent TTL 節流。
4. CI 必須驗證只初始化 `Shioaji(simulation=True)`、禁止 `simulation=False` 與盤中 `snapshots()`、指數 `IX0001`、同代號多次請求只訂閱一次、MIS 缺成交不補昨收、TSE/OTC 隔離、Owner 讀價與 singleflight 正反例。
5. Dev 上線須有 migration 073、Proxy/Janus API/Flutter 的同版 CI 與部署實際收據；並驗證登入後 Today、關注、持股、個股，20 個同時 Owner session 相同標的僅單一上游更新，以及休市／背景／斷線的停用與降級。**文件、commit 或 Proxy Ready 不是全案驗收完成證據。**
