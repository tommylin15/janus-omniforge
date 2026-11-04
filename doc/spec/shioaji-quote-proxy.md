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
