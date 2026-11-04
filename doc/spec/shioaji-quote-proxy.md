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
