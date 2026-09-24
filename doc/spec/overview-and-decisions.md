# Janus SPEC — 產品目標與架構決策

## 1. 產品目標

建立以台股為主的個人投資工作台與湖倉型智慧投資研究平台。第一優先是讓使用者安全管理交易記帳、個人筆記與關注股；通用 AI 對話由 omniAgent 負責，Janus 提供經授權的投資 API／MCP context。後續以官方與核准 fallback 資料產製市場、板塊、話題與候選股研究 Mart。

User 與 Admin 是不同的 navigation、workspace state、token audience 與 backend authorization
surface，但目標是共用單一 Flutter codebase；Flutter 的公開研究頁只讀取符合發布政策
的公開 Mart 成品，私人記帳、筆記與關注股只讀取 authenticated user 的
ledger／Private Core／Mart。現有 static HTML／JS Admin 在 migration 期間保留，直到
Flutter parity、Admin auth、browser/runtime acceptance 與 rollback plan 完成。兩者均只經 FastAPI 契約取用已持久化資料，不直讀 Stage，也不在一般
page load 內觸發即時爬取、Agent 或 LLM。

個人投資工作台是 User App 的第一優先私人功能。PostgreSQL append-only ledger 保存需要 OLTP 一致性的交易事實、冪等鍵與單調遞增 `ledger_version`；筆記正文、關注名單歷史與交易正規化資料儘可能保存於 Private Iceberg Core，PostgreSQL 只保留必要的目前狀態、索引、版本、工作狀態、checkpoint 與 artifact reference。Private Mart 計算庫存、成本與損益；同步失敗可從最後成功 checkpoint 重跑，不另建 outbox。私人資料不得進公開 Mart／service index、話題、排行榜或他人的分析。

資料供應採雙軌策略：以全市場約 1,700–2,000 檔的低成本日頻資料作為搜尋與篩選大網，再對使用者主動加入關注名單的標的收集經核准的深度資料。深度追蹤不再代表「50 大」或平台推薦；MVP 仍以最多 50 個 active distinct symbols 作成本／quota 技術護欄，實際檔數以有效關注需求、股票 master 與市場狀態為準。

系統是研究、風險提示與手動交易筆記工具，不是自動下單、券商帳戶同步、持牌投顧或保證獲利服務。

### 1.1 交付順序

1. 先完成個人工作台所需的最小 Dev Stage → Core、股票 master、User auth 與 Private Iceberg 基礎；WBS 3 其餘 Admin polish／全市場擴張不得阻擋私人 MVP。
2. P0 交付交易記帳、個人筆記、關注股與最小 Flutter；正式損益只讀 Private Mart，私人長內容儘可能進 Iceberg。
3. 通用多供應商私人助理由 omniAgent 擁有，不屬 Janus 部署或 runtime；Janus 維持投資 domain API 與 authenticated read-only MCP／OAuth connector。
4. Chat thread、provider、model、Skills 與對話 lineage 由 omniAgent 管理；Janus 不保存或管理 omniAgent conversation lifecycle。
5. 完成私人 MVP 後，再執行全市場深化、公開 Intelligence Mart、公開研究 UI 與發布流程。

### 1.2 Dev Pilot before Production

MVP／Dev 驗收通過後不得直接進入 production。Janus 先在既有 Dev topology
執行 6 個 calendar months 的 Dev Pilot，持續累積真實資料、分析結果、可靠性、
維運與成本 evidence。Pilot 起始日不是本文件修改日；只有 Pilot Entry Gate
實際通過時才記錄 `pilot_started_at`。

Pilot 期間不要求建立 staging 或 production environment，也不因 Pilot 自動升級
PostgreSQL Free Tier VM、建立 HA／replica／backup infrastructure 或其他
production-only GCP component。既有 `e2-micro` PostgreSQL 仍是 Dev／MVP 配置，
不是 production HA architecture；任何 paid GCP resource 仍需人工同意。

Pilot 完成後，依實際 workload、reliability、cost、security 與 operations
evidence 重新評估 production architecture，並由人工 Go／Extend／No-Go review
決定；不得自動 promotion。omniAgent 的 production gate 由其自身治理文件管理。

### 1.3 Janus ChatGPT MCP Connector

ChatGPT Custom MCP App 定位為 Janus 的 external read-only data consumer，供經
Janus 驗證身分的 owner 讀取已核准的 public market data 與自己的 private
investment data 進行分析。它不是 Janus 的第四個 AI provider／runtime，不是
Janus MCP Host、Skill runtime 或 Chat API thread，也不建立新的分析資料庫；不要求
OpenAI API key。

首選 topology 為 `ChatGPT → remote read-only MCP → existing janus-api → shared
bounded context/query boundary → existing Public Core/Mart、owner-scoped Private
Core/Mart 或 bounded journal reader`。ChatGPT 不得直接連 GCS、Iceberg catalog 或
PostgreSQL，不得傳 SQL、table name、GCS URI、object path、`user_id`／`owner_id` 或
credential locator，也不得執行 Admin、journal、note、watchlist、下單、ingestion
或 analysis mutation。第一版完全 read-only，且不預設新增 `janus-mcp` Cloud Run
service。

Janus API 的 MCP／OAuth endpoint 與 metadata 已在 GCP dev 通過候選及 canonical
驗收；互動式 consent 與 authenticated tool call 尚未完成。ChatGPT connector 不是
Janus Production Release 的必要條件。詳細剩餘 gate 見
[omniAgent split status](../omniagent-split-status.md)。


### 1.4 Pilot Scope Freeze

最新 scope control policy 為：停止擴功能，先補齊 4 個 Pilot readiness gap，完成
ChatGPT MCP，啟動 6 個月 Dev Pilot，六個月後再依實際 evidence 決定哪些功能值得
留下，以及是否進入 Production planning。這不是刪除已完成 code，而是停止繼續投入
尚未證明 business value 的功能擴張。

六個月 Pilot 開始前與期間，以下 Janus 項目維持 feature freeze：Mart 核准五角色
以外的新 AI roles、更多 Janus MCP workflow、未核准的
額外 analysis dashboard、未核准社群／Podcast／alternative-data adapter、額外 UI
cosmetic polish、Pilot 實際不用的平台完整 A11y／device matrix、新 GCP service、
HA／replica／multi-region／GKE，以及為架構漂亮而新增 infrastructure。

Freeze 不代表刪除現有 code。允許 correctness、security、data-integrity、cost
regression、Pilot blocker fix，以及維持既有功能正常所需的最小 maintenance。
OpenRouter、Gemini、Codex、MCP Host、Skills 與通用助理 runtime 歸 omniAgent 所有；
Janus 僅保留 domain API 與外部 MCP connector。未完成的舊 WBS-4C 擴張不再是
Pilot Entry blocker。

### 1.5 Supply-chain Intelligence 核心研究方向

Supply-chain Intelligence 是 Janus 的核心差異化研究方向，目標是結合供應鏈關係、
leading indicators、company exposure、PIT data、market expectation 與個人 portfolio
context，尋找 demand／earnings inflection 與 market expectation gap。主要時間尺度是
days／weeks／months，不追求 ultra-low-latency trading，也不是另一套一般財經資料平台。

六個初始研究 domain 全部進入 roadmap，但共用同一套 architecture，不代表 Pilot Day 1
必須同時具備六套 ingestion pipeline：

| Domain | 初始研究鏈（ontology seed，非已證實關係） |
|---|---|
| AI Server／Semiconductor | demand → GPU／ASIC → foundry → advanced packaging → PCB／ABF／CCL → power／cooling → ODM |
| Memory | end demand → DRAM／HBM／NAND → wafer → packaging／testing → module |
| EV | EV demand → OEM → battery → power semiconductor → motor／inverter → connector／PCB／charging |
| Networking | cloud／datacenter demand → switch／router → ASIC → optical → PCB → connector |
| Apple supply chain | Apple product demand → assembly → SoC → camera／display → PCB／components |
| Industrial automation | manufacturing cycle → PLC／servo／robot → motor／drive → sensor／components |

共用流程為 `External／Official Data → Stage → Core → relationship model → leading
indicators → company exposure → expectation signal／gap → Mart → Janus／ChatGPT analysis`。
優先重用既有 GCS、Iceberg、DuckDB／PyIceberg、Cloud Run jobs／services、Mart、PIT、
provenance 與 immutable snapshot／baseline；第一版不新增 Graph DB、Neo4j、BigQuery、
Cloud Run runtime 或其他 paid GCP resource。

Pilot Scope Freeze 的明確例外只允許 architecture／spec planning、ontology design、
source matrix research、seed graph planning 與 Pilot measurement design。production
ingestion、crawler、未核准 adapter、paid source、tick／high-frequency source 與新 GCP
resource 仍 frozen／deferred，並須依 WBS-5／WBS-8 的 unlock gates 個別解鎖。

## 2. 已確認的架構決策

- Janus 市場資料與 API 在 GCP 開發、測試與部署；通用私人助理由獨立的 omniAgent 負責。Web／mobile client 只經 authenticated HTTPS 連線。
- 一個 GitHub monorepo，市場資料、智慧 Mart、私人帳本、API、User 與 Admin 保持清楚邊界；Core query 能力由 Job／API 各自內嵌的 DuckDB runtime 提供。
- User／Admin 使用單一 `apps/user_app` Flutter + Material 3 codebase，但維持不同
  navigation、route guard、token audience、CORS、backend authorization 與 audit；
  現有 `apps/web` static Admin 僅作 migration compatibility，parity 完成前不得刪除。
- Dev User authentication 固定使用 Google OIDC／Google Sign-In，使用獨立於 Admin 的 OAuth client／audience。API 驗證 issuer、audience、expiry，並以 `(provider="google", subject=sub)` 對應內部 UUID `user_id`；email 只供顯示，不作所有權鍵。Dev 可另加 User allowlist，不建立自有密碼系統。
- `services/api` 以 FastAPI 提供 public、private-journal 與 Admin API router；共用 service／repository 時仍使用不同路由、response model、認證、CORS、IAM 與 audit 邊界。現有 WSGI boundary 保留至 FastAPI 回歸測試完成後移除。
- GCS + Iceberg + DuckDB／PyIceberg 是資料主架構；DuckDB 不作為獨立持久資料庫。
- PostgreSQL 保存 Iceberg catalog、控制、治理、execution、publication、audit、服務索引與私人交易事件帳本；市場 raw payload 與完整 Mart payload 仍不進 PostgreSQL。
- Dev／MVP PostgreSQL 採 Compute Engine `e2-micro` 單一 VM 自架，位於 `us-central1`；Free Tier 模式限制 Standard Persistent Disk 總量 ≤30 GB、不配置 external IP，並以 IAP／OS Login 管理。此配置不作為 production HA 架構。
- `e2-micro` 僅承載 PostgreSQL，不承載 DuckDB 分析工作；DuckDB 內嵌於 Cloud Run Job／Service process，暫存與記憶體限制由各 runtime 獨立管理。
- 開發／重構期最低有效完整度為 30%；正式發布門檻日後依 PIT 回測與人工治理調整。
- Mart AI analyst／CIO 可對 supplied Fact Pack 做 evidence-grounded analysis、
  contradiction explanation 與 synthesis；不得計算或修改 canonical deterministic
  numbers／facts、補值、宣告 publication 或改 governance outcome。
- 通用私人助理、provider dispatch、Agent Gateway、Skills 與 Codex runtime 均由
  omniAgent 負責；Janus 不包含其 UI、runtime、thread lifecycle 或 storage。
- Janus 提供 remote read-only MCP／OAuth endpoint；Janus 不是 MCP Host，不持有通用
  Skills／approval／thread runtime。Janus 與 omniAgent 的資料及 auth 邊界見
  [API 與交付](api-and-delivery.md)。
- Janus API、Jobs 與 PostgreSQL migration build 使用單一 `janus-runtime-bundle`；
  GCP dev 欄位與 IAM 現況見 [Secret 清單](../secret_list.md)。不得將舊 Agent
  provider／Codex auth bundles 寫成現況。
- Cloud Run Service 全部 `min-instances=0`；寫入 Core 的 ingestion Job 單 task 執行，API／query runtime 對 Core 採 read-only。
- Artifact Registry 可由 source deploy／Cloud Build 自動管理，但底層仍需保存容器映像。
- Artifact Registry 僅使用 image、digest、metadata 與 cleanup；禁止 Artifact Analysis API、Container Scanning API、vulnerability scanning 與 occurrence API。SBOM 僅可離線產生，不以掃描結果作為 build gate。

## 2.1 Approved Mart Analysis Profile design (Planned)

Analysis Profile 是 versioned immutable configuration，包含 provider、model、可用的
reasoning level、bounded output length、provider-supported parameters、五個 role prompt
version、CIO prompt version、per-role override 與 hashes／lineage。唯一 Admin 可直接
建立新的 Production version；不可覆蓋舊版本，rollback 也建立 audit／version lineage。
System Guardrail 永遠 locked；Role Methodology／CIO Prompt 可編輯；Output Schema 由
系統控制。固定 5–10 檔 test symbols 用於 current Production 與新 version 的比較，
不是 Candidate approval gate。這些皆為 Planned，與目前 Gemini narrator／static Admin
current truth 分開。

## 2.2 Mart analysis scope guardrails

Fact Pack、AI interpretation 與 governance publication 永遠分層保存。`mart.v1` 維持
相容；新 artifact／validator contract 先以 additive layer 規劃，只有 migration
contract 與 tests 完整後才升版。Leading Indicators 與 Major-wave Prediction 不加入
目前五角色、CIO、score 或 publication；最多保留 extensibility，屬後續 Research／
Pilot Evolution。

## 2.3 Research Context 產品方向（Pilot Evolution）

Janus 將正式或已核准外部資料依 `Stage → Core → deterministic Mart／Supply-chain
Intelligence → bounded ResearchContext → existing janus-api` 提供給 User App 與
read-only ChatGPT MCP。私人資料沿用 PostgreSQL control／ledger、Private Core／Mart
與 owner isolation。`ResearchContext` 是 server-side composed output contract，不是新資料庫、
新 pipeline 或 ChatGPT-specific data platform。

Google Drive 中的投資研究資料僅作外部需求參考；不作 runtime source、
source of truth、sync／ingestion 目標或 MCP dependency。本方向全部分類為
**Pilot Evolution**，不新增 Dev Pilot Entry blocker。Supply-chain Intelligence 仍沿用
Gate A–E；社群、Podcast、廣泛另類資料、昂貴付費研究與高頻基礎設施
為 Post-Pilot Conditional。
