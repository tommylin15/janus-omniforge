# Janus SPEC — API、User、Admin 與交付

更新：2026-10-03

## 12. User、Admin 與 API

User 與 Admin 共用 `apps/user_app` Flutter／PWA codebase，但維持不同 workspace／navigation、token audience、CORS、backend authorization 與 audit boundary。2026-10-02 已退役 legacy static HTML／JS Admin；它不再是 active fallback、parity gate 或 runtime。

FastAPI 為共用 HTTP boundary：

- `/api/v1/public/*` — publishable public data；
- `/api/v1/me/*` — authenticated owner private data；
- `/api/v1/admin/*` — Admin control／operations。

三者分離 response model、auth、rate limit、CORS 與 audit policy。Flutter hidden control 不是 security boundary。

### 12.0 基本 API 規則

- public endpoint 不直讀未發布／blocked artifact，不暴露 catalog owner、control schema、raw object URI、credential locator。
- private endpoint 的 owner 只由已驗證 token 綁定，不接受 query／body 指定 `user_id`／`owner_id`。
- Admin request 每次由 backend enforce Admin authorization；Admin 身分不自動取得 user trade／position 正文讀取權。
- 404／missing 不觸發 scraper、Agent 或 LLM。
- Admin mutation 只建立 bounded control／queue／command，不在 request 內同步執行長任務。
- response／log 不暴露 raw payload、secret、token、password、private key、完整 traceback、private artifact locator。
- partial／stale／blocked／unknown 不得包裝成 success／0。

### 12.1 Public research API

現有／相容 public surfaces 由 GitHub `main` implementation 決定，UI contract 至少包含：

- `/api/v1/public/health`
- `/api/v1/public/market-home`
- `/api/v1/public/stock-header/{symbol}`：enabled symbol 的正式主檔名稱與最新持久化 OHLCV 收盤價／交易日；最多讀一列，缺價明示 missing，不依賴 specialist／CEO report。顯示為歷史收盤價，不冒充即時報價或今天行情。
- `/api/v1/public/daily-brief?date=YYYY-MM-DD`
- `/api/v1/public/sectors/rotation?date=YYYY-MM-DD`
- `/api/v1/public/topics?date=YYYY-MM-DD`
- `/api/v1/public/candidates?date=YYYY-MM-DD`
- `/api/v1/public/stocks/{symbol}/health`
- `/api/v1/public/stocks/{symbol}/reports`
- `/api/v1/public/stocks/{symbol}/kline?period=D|W|M`
- `/api/v1/public/stocks/{symbol}/events?cursor=...`

`market-home` 的 deterministic benchmark／market activity／institutional sections 可有各自 data date／freshness／coverage／provenance；Mart／Daily Brief 未就緒不得讓 baseline 不可用。

`market-home` 在單一 API instance 內使用最多 60 秒、一筆公開摘要的有界快取，保留原資料日／freshness；不快取私人資料或認證結果，不建立第二個 canonical store。Instance 冷啟動／cache miss 的 Core 查詢時間另列，不宣稱為暖機命中效能。

Public report 只讀 publishable／published artifacts；`blocked`／`insufficient_data` 不進公開 service index。

### 12.2 Private User API

Owner-scoped surfaces 包含交易、筆記、watchlist、positions、PnL、portfolio、investment profile、private-data export／deletion 等既有 contract。

Private Mart 的有界讀取可在 instance 內重用最多 32 組 exact-snapshot scan；key 包含 table、snapshot ID、owner、filter 與 limit，每次仍讀 current snapshot pointer 並執行 current ledger version freshness gate。新 snapshot／owner／ledger mutation 不得命中另一個身份或以舊資料冒充最新；notes／無界 pipeline scan 不快取，回傳資料與 cache 分離，避免呼叫者修改污染後續讀取。

Operational Quote Router 與 owner-scoped Broker Profile 的資料來源、版本、
missing／stale／fallback 與 export／deletion 契約見 [行情與券商設定](quotes-and-broker-profile.md)。

重要語意：

- ledger append-only；correction 建立 reversal／replacement，不無痕覆寫。
- mutation 成功首先代表 ledger／note／watchlist 等 domain write 已持久化；不等於 Private Mart 已完成 valuation／PnL 重算。
- operational position projection 可同步反映 shares／average cost／cash impact；canonical valuation／PnL／exposure／performance 只讀 Private Mart。
- private aggregate 不可靠時由 backend withheld 並回 bounded diagnosis；Flutter 不自行忽略缺值加總。
- private delete 使用 auditable／retryable flow；`CLEANUP_PENDING` 不得顯示 completed。

Janus 不提供 `/api/v1/me/chats/*`、generic Agent／Skills／approval runtime。

## 12.3 Stock Detail specialist／CEO contract

### 五 specialist

五 specialist production 主路徑為 Python／SQL／ML；User／Admin 只讀 persisted／validated artifacts。API 不提供「每日五個 LLM roles」作為 active execution model。

specialist read contract 至少保留：

- symbol／specialist type；
- `analysis_as_of`／data as-of；
- status／freshness；
- structured metrics／drivers；
- missing／stale／partial；
- model／engine／artifact version；
- evidence／provenance references。

### On-demand CEO

CEO command／report contract 是 additive capability；對應 WBS 尚未完成時不得假裝 endpoint 已 live accepted。

command 至少檢查：

- authenticated user；
- DB-backed capability（例如 `ceo_analysis.request`）；
- symbol／profile；
- in-flight duplicate guard；
- quota／cooldown；
- approved provider／model／profile；
- bounded timeout／retry policy。

request accepted 只代表 execution 已建立，不代表 report succeeded。每次分析／重新分析建立新的 immutable execution/report，舊 report 保留。

CEO 只讀 latest validated specialist outputs／Fact Pack／provenance，不計算或覆寫 canonical number，也沒有 publication authority。upstream specialist change 只標記 CEO report freshness／material delta，不自動觸發 CEO。

## 12.4 Admin API

Admin UI 依 `../ui/admin.md`，主導覽目標為：

- 總覽
- 批次
- 個股
- 市場資訊
- AI 分析
- 資料治理

Admin API 需 bounded 支援：

- actionable issues；
- effective batch／occurrence／execution details；
- retry classification／retry lineage；
- source／dataset health；
- market universe；
- Stage／Core／Mart／必要 Private operational governance；
- retention／maintenance／storage telemetry；
- specialist model／evaluation status；
- CEO provider/profile/capability/quota/cooldown/usage audit（對應 WBS 完成後）。

manual retry／rerun 必須經 backend allowlist、authorization、idempotency／duplicate guard、dependency／exclusive guard 與 audit。Flutter 不傳任意 Cloud Run job name、checkpoint、bucket／object path。

## 12.5 Analysis Profile

現行 Analysis Profile 管理：

- specialist champion／model／version／evaluation；
- CEO provider／model／profile／route；
- immutable version／history；
- compare／rollback／audit；
- bounded test symbols／evaluation evidence。

`Codex CLI → OpenRouter → Gemini` 只屬 On-demand CEO／approved escalation，不再代表五 specialist daily route。

Profile mutation 建立新 immutable version；不能覆寫舊 execution 的 effective config。rollback 也建立新的 audit／version lineage。

## 12.6 Janus／omniAgent runtime ownership

Janus 負責投資 User／Admin、domain API、bounded context、authenticated MCP／OAuth；MCP 只提供 bounded read，不提供個人交易／股息寫入。Generic Chat UI、provider dispatch、Agent Gateway、Skills、approval、Chat persistence 由 omniAgent 負責。

歷史 Janus Chat writer/runtime 已移除；既有 migration／historical private data 的存在不代表仍有 active Chat API。任何歷史資料清理仍需依 private-data／retention contract，不能因 runtime 退役自動大量刪除。

## 12.7 Janus ChatGPT MCP Connector

ChatGPT MCP 是 external authenticated client／consumer，不是 Janus 第四個 AI runtime、MCP Host、Skill runtime 或 Chat thread；不加入 CEO provider loop，也不保存 ChatGPT conversation snapshot 到 Janus Private Iceberg。只允許三個 bounded read tools。

首選路徑：

`ChatGPT → remote MCP → existing janus-api → shared bounded query boundary`

不新增 `janus-mcp` Cloud Run service。

### 12.7.1 Tool surface

三個 logical tools，全部 read-only：

- `janus_sources`
  - input：空 object。
  - scope：`janus.sources.read`。
  - 回傳 principal 可用 source/resource、freshness、status、quota／bounds／disclosure，不回資料內容或 storage locator。
- `janus_market_context`
  - scope：`janus.market.read`。
  - required：`symbol`、`resource`。
  - `resource`：`ohlcv`、`valuation`、`institutional`、`financials`、`events`、`market-activity`、`benchmark`。
  - optional date range 最長 366 天；`limit` 1–20，default 10。
  - 不接受 table／dataset／URI／offset／raw query。
- `janus_private_context`
  - scope：`janus.private.read`。
  - `resource`：`positions`、`annual-pnl`、`exposure`、`performance`、`stress-tests`、`investment-profile`、`watchlist`、`trades`。
  - optional `symbol` 只適用 positions／watchlist／trades；`year` 依 resource contract；`limit` 1–20，default 10。
  - `investment-profile` 只有既有 AI context opt-in 時回傳；第一版不暴露 free-form notes。

三個 read tools 共用 envelope：

```json
{
  "schema_version": "janus.mcp.v1",
  "status": "available|partial|missing|stale",
  "resource": "allowlisted-resource",
  "as_of": "ISO-8601-or-null",
  "records": [],
  "provenance": [],
  "bounds": {
    "limit": 10,
    "returned": 0,
    "truncated": false,
    "max_output_bytes": 32768
  },
  "disclosure": "source and external-AI disclosure"
}
```

records 最多 20 筆／32 KiB；超限只在完整 record 邊界截斷並明示 `truncated=true`。provenance 只回非 locator metadata，例如 `source_id`、`provenance_id`、`snapshot_id`、`ledger_version`、`valuation_date`。

### 12.7.2 MCP auth／owner boundary

- 所有 tools 都要求 authentication，包括 public market tool。
- request 不接受 `user_id`／`owner_id`／Google `sub`／email／Secret name／credential locator。
- owner 由 server 驗證後的 issuer／subject binding 映射 internal UUID；email 不作 owner key。
- OAuth token 必須綁 MCP resource／scope；Google browser ID token boundary 不直接當 MCP bearer boundary。
- canonical MCP resource 由 trusted deployment config 固定，不從 request `Host` 推導。
- output 不回 GCS URI、object path、raw payload、credential、password、secret、token、private artifact locator、internal owner ID。
- private data 送 external AI 必須有清楚 disclosure；不預先替外部平台宣稱 retention／training policy。
- 2026-10-09 使用者撤除 MCP ledger write：不列出或執行 `janus_private_ledger_append`，不再接受新 OAuth `janus.private.write` 授權；舊 token／外掛快取也不得恢復寫入。User App 的既有記帳 API 不受影響。

現有 `/mcp` adapter 只處理必要 initialization／ping／tools/list／tools/call 與 notifications；不提供 ledger write、generic mutation、resources、prompts、subscriptions、approval runtime 或 conversation snapshot storage。

## 12.8 ChatGPT Mobile Ledger Bridge

目前 ChatGPT mobile 不載入自訂 MCP tool，因此手機對話的 ledger 寫入不假裝沿用 desktop MCP。mobile path 使用已安裝的原生 Google Drive connector 作為受限 command queue：

`ChatGPT mobile → janusChatGPT/Janus Mobile Ledger Queue → existing hourly batch controller → janus-private-pipeline → canonical private.ledger_events`

治理契約：

- queue 是私人 Google Sheet，固定名稱與固定 schema；runtime 只掃描既有 Sheet 前 1000 列（header + 最多 999 筆 request）、每輪最多處理 20 筆 `PENDING`。
- ChatGPT 只寫使用者明確提供／可驗證的交易值；`fee`、`tax` 必須明確填值，空白不自動補 0。缺年分、費稅拆分或其他 canonical 欄位時不得 enqueue。
- row 不接受 owner selector。Private Pipeline 由 Drive file owner email 對應既有 Janus user；找不到或不唯一時 fail closed，不建立新 user。
- `request_id` 直接作 canonical ledger idempotency key；DB 已成功但 Sheet status 更新失敗時，下一輪 replay 不得重複交易。
- existing hourly `janus-batch-controller` 只在 queue 有 pending row 時條件式觸發既有 `janus-private-pipeline`，不新增 Scheduler／Cloud Run resource；weekday 21:30 原 Private slot 同時是 fallback，且同 slot 不重複 dispatch。
- queue provider unavailable 不阻斷原 Private Mart 排程；mobile request 留在 `PENDING` 等下一輪。invalid／oversell 等 domain error 回寫 bounded error code，不把 private holdings 或 provider raw error 寫入 Sheet／一般 log。
- Private Pipeline 先 consume ledger queue，再跑既有 change-log Private Mart refresh，因此成功 write 可在同一 execution 進入 holdings/report refresh chain。
- 此路徑仍然只是 Janus 記帳，不向券商下單、不移動資金；更正／刪除不經 mobile queue，仍走正式 correction/private-data contract。
- Google Drive／Sheets 只作 mobile command ingress，不取代 PostgreSQL canonical ledger、Iceberg Private Mart 或 MCP read path。

## 13. GCP 開發與 CI/CD

| 項目 | 現行原則 |
|---|---|
| 原始碼 | GitHub monorepo、目前 `main` 單 branch 工作方式 |
| GCP 認證 | workload identity／runtime identity；不使用長效 JSON key |
| Build | Cloud Build／GitHub Actions 依現行 workflow |
| Image | Artifact Registry、immutable digest |
| Dev deployment | 既有 dev topology；完成需 live acceptance |
| Secret | Secret Manager，最小 workload access |
| IaC／scripts | idempotent；新付費／production重大變更需人工授權 |

API telemetry 只記 router family、method、status、duration、server-generated request ID 等 bounded metadata；query／body／token／object URI 不進一般 log。

Job completion 可記 execution／trace ID、duration、retry、publication／row counts 與 bounded error taxonomy。Admin detail 可串 UI → Job → Core → Mart lineage，但不暴露 raw payload／storage credential。

## 13.1 Dev PostgreSQL

- 目前 dev PostgreSQL 用於 control、catalog、publication、audit、private ledger 等低併發 metadata／OLTP；GCS／Iceberg 不搬入 PostgreSQL VM。
- private connectivity，禁止公開 `5432`。
- resource／disk／backup／HA 仍依目前 dev contract；新增付費或 production HA 需人工核准。
- bounded query、retention／export、容量與連線控制必須維持。
- PostgreSQL 不承擔 DuckDB analysis workload。

## 13.2 Artifact／supply-chain guard

- build／deploy 不得為了掃描或 UI 方便自動啟用未核准付費 API／service。
- schema evolution、migration、backfill、destructive cleanup 不隨一般 API／Flutter deploy 隱式執行。
- secret／token 不進 image、Git、一般 log 或前端。

## 13.3 ResearchContext composition（Planned）

`ResearchContext` 是 existing `janus-api` 上的 typed、bounded、owner-scoped、PIT／provenance-aware composition contract，不是新 storage layer。

概念 sections：

- `market`
- `company`
- `supply_chain`
- `private`
- `quality`

全部使用同一 `analysis_as_of`，明示 missing／stale／partial／freshness／provenance。private section 由 authenticated principal 綁 owner；不接受 owner ID。不得輸出 credential、SQL、table name、GCS URI、object path、raw payload。

UI 與 MCP 可共用同一 bounded semantics；Google Drive 不作 runtime dependency。未列入 active TODO 前不得把 proposed endpoint 當成已實作。
