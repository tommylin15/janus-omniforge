# Janus SPEC — 非功能需求與 Release Gate

## 14. 非功能需求

- 冪等、可重跑、可追溯、可安全失敗。
- Stage → Core 寫入前的 required key、type、duplicate、time／future-leakage 與 quarantine 屬不可延後的安全邊界；完整跨源校準、quality score、DQ dashboard 與門檻調優排在 Admin／Flutter User UI 自動化、實機與 A11y 驗收之後。
- GCP services 同區以避免跨區成本。
- 統一 execution／trace ID；log redaction。
- 監控來源成功率、latency、freshness、schema drift、fallback、Job 狀態、publication 與 API error。
- 設定目前 Dev 使用的 single TWD 320 notification budget，threshold 為 10%／50%／100%；budget 是 notification，不是 spending cap，actual spend 以 Cloud Billing 為準；另維持 GCS lifecycle、Artifact Registry cleanup 與 Workstation 自動停止，不新增 paid BigQuery billing export。
- 不宣稱固定 $0；費用以當期定價與實際帳單為準。

### 14.1 目前 Dev 的 release 語意

- 目前 GCP `dev` 是個人使用階段的平行上線環境，因此「可用／已發布到目前環境」可由實際 dev deployment、真實資料、OAuth、API、MCP／provider、Job／Scheduler 與 UI runtime evidence 判定；不需要先建立另一套名為 production 的環境才算真實可用。
- 未來的 `Production` gate 僅用於對外、多使用者、HA／SLA、正式營運或需要更嚴格隔離的階段；它與目前個人能否在 dev 真實使用是兩個不同判定。
- mock／fixture／localhost 不能取代 real-path acceptance；但可補充真實服務不適合故意製造的 timeout、cancel、disconnect、secret-redaction 等故障情境。
- dev 內包含真實個人資料，因此 secret、owner/auth、migration、備份／可重建、不可逆刪除防護與 partial-success honesty 不因名稱是 dev 而降低。

## 15. Release Gate

本節的 gate 是「能力是否可在目前平行上線 dev 真實使用」的主要驗收基準；若某能力只規劃給未來多人 Production，則另依該能力的 Production scope 判定。

- 2330 完成 Source → Stage → Core → Mart → API → UI 閉環。
- 同一 `analysis_as_of` 可從 `mart_daily_brief` 追溯市場狀態、板塊輪動、熱門話題、候選股及其 Core／Mart snapshot。
- 私人交易可從 PostgreSQL ledger 重建 Private Core／Mart；跨年損益、更正事件與所有權隔離通過測試，且不出現在 public index。
- 筆記、關注歷史、chat messages、context snapshot 與 citations 可從 Private Iceberg 依 authenticated user 讀取、匯出與刪除；PostgreSQL 不保存正文或完整對話 payload。
- 目前個人 live scope 只要求實際啟用的 runtime／capability 通過對應 real-path gate；每項必須是 `enabled and accepted`，或明確 `disabled`，不得停留在 UI 可選但 backend 不安全或只用 mock 證明的狀態。對啟用項目應依其風險驗證 Cloud Run scale-to-zero／cold start／timeout／重連、Core／Private／外部資料源 provenance、Janus MCP／OAuth／privacy 等對應能力；omniAgent Skills／runtime 只由 omniAgent 驗收。ChatGPT MCP 或尚未 productionize 的能力不應阻擋與其無關的既有個人功能。
- PIT 無 future leakage；排除樣本有原因與 provenance ID。
- blocked 不進公開 latest／history；查無資料不即時運算。
- 兩個 Job、FastAPI、Flutter User／Admin workspace、migration 期間的 static Admin 與各
  內嵌 DuckDB runtime 的 IAM、timeout、retry、監控與 rollback 通過；static Admin 只有
  在 Flutter parity 後才可退役。
- 全市場日頻與個人關注股深度 membership／cadence／50-symbol 營運護欄通過驗證；Admin 看不到 user-to-symbol 對應，未核准的高頻、新聞或社群來源保持 disabled／blocked。
- pytest、FastAPI contract tests、Flutter analyze／test、Vitest、Playwright、TypeScript 與受影響 runtime build 通過；只有未來獨立 Production 發布才另外要求對應 production build／promotion gate。
- 目前實際使用裝置／瀏覽器的主要流程通過；完整 iOS Safari、Android Chrome、iPad Safari、VoiceOver、TalkBack、WCAG AA matrix 可依實際個人使用需求分階段補齊，不作所有 dev 個人功能的共同前置 blocker。
- 無 secret、raw payload、敏感 URL、未授權來源外洩。
- 私人資料刪除狀態可查詢；`CLEANUP_PENDING` 不顯示成功，且 Iceberg snapshot／orphan file、GCS object version 的實際清除期限已有 GCP dev 證據與使用者文案。
- runbook、重要資料的 bounded backup／export／可重建路徑與必要 rollback 已定義；高可用、PITR、跨區備援等屬未來 Production 需求，除非另行核准不作目前個人使用 blocker。

### 15.1 Planned Mart AI acceptance

- 相同 immutable facts、prompt/model/profile identity 可追溯且可 reproducible；LLM off
  不改 deterministic facts。
- AI 不得修改 canonical numbers；schema、evidence ID、numeric grounding、time fence、
  missing-data honesty、claim coverage 與 provider/model/prompt lineage 失敗時不得 publish。
- one-role failure 不得宣稱 five-role full success；single-role rerun 不重跑無關 role；
  prompt/model change 不重算 facts；governance-only change 不重跑 LLM。
- content-addressed reuse、old artifact immutability、Gemini／OpenRouter provider
  contract、unsupported model／parameter、billing gate、retry bounds、429／unavailable
  structured failure 均須有測試。
- Admin API 每次 backend authorization；Flutter hidden control 不作 auth；Analysis
  Profile version、rollback、fixed 5–10 symbol comparison、historical analysis 與 retry lineage 均須可驗收；未來若有獨立 Production direct update，再另加 promotion／rollback gate。

Leading Indicators 與 Major-wave Prediction 不屬本次 release scope，未實作、未納入
score／CIO／publication，也不作目前個人 live 使用 blocker。

## 16. Production Readiness／Dev Pilot Evidence Window

目前 `dev` 已被定義為個人使用階段的真實平行上線環境。Pilot Entry Gate 與六個 calendar months 的 Dev Pilot 是「建立 baseline、持續收集真實資料／可靠性／成本／模型價值 evidence」的治理與決策機制，不是阻止使用者在此期間真實使用已通過能力的環境閘門。

只有要建立未來獨立 Production topology、擴到多人／對外、引入 HA／SLA 或明顯增加成本與權限時，才需要 `Production` Go／No-Go 判定。Pilot 期間不要求 staging 或另一套 production environment，也不因某個與日常使用無關的 Pilot checklist 未完成，就把已在 dev real-path 驗收的功能降格成「只能模擬」。

Pilot ledger durability 使用已人工核准的 bounded logical backup strategy：
`pg_dump → restricted Private GCS`。這不代表 Dev 具備 HA／PITR，但因 Dev 保存真實個人資料，至少要保留實際可用的 restore／rebuild evidence；不得因追求 production 級基礎設施而自動新增付費 persistent resource。

Pilot evidence 至少涵蓋以下類別；本節只定義 evidence scope，不預設尚未決定的
pass threshold：

- Data：ingestion success／failure、freshness、coverage、missing data、schema
  drift、quarantine／retry、source stability。
- Analysis：result availability、deterministic／reproducible portions、
  provenance／citations／source coverage、適用時的 PIT／future-leakage evidence、
  model／provider／analysis revision lineage、5／20／60 trading-day outcome、
  relative benchmark、MFE／MAE、valid／excluded status、exclusion reason、
  provenance、usefulness feedback，以及 Pilot baseline／version grouping。
- Runtime／Operations：Cloud Run Job／Service 與 Scheduler reliability、retry／
  idempotency、適用時的 cold start／timeout／reconnect、manual intervention
  frequency 與 recurring operational failures。
- Cost：actual Cloud Billing evidence、可取得時的 provider usage／cost evidence、
  resource growth trend；billing budget notification 不等於實際 spending cap。
- Security／Privacy：secret handling、owner isolation、auth lifecycle、private／
  public data boundary，以及 relevant delete／cleanup evidence。

每份用於 Pilot 判斷的重要分析結果，都必須能從現有 metadata 或 lineage 合理
追溯 data／snapshot 或 analysis time boundary、relevant source／provenance、
application／code／image revision、適用時的 analysis／skill／config revision
與 provider／model、execution identity／time，以及 result status／material warning。
這是 logical evidence requirement，不建立特定 database column 或 storage implementation。

六個月 evidence window 完成後，人工 review 至少回答：資料是否足夠可靠、分析是否具有持續使用價值、系統是否能長期自動運作、維運負擔是否可接受、實際成本是否與價值相符，以及是否真的有必要建立獨立 Production architecture。Outcome 為 `KEEP_DEV_PARALLEL_LIVE`、`GO_PRODUCTION_PLANNING`、`EXTEND_EVIDENCE_WINDOW` 或 `NO_GO`；任何 outcome 都不得自動建立 production resource。

`GO_PRODUCTION_PLANNING` 只允許開始未來 Production architecture／migration planning，不能取代後續明確的人工作業與成本批准。若個人使用情境持續適合目前 `janus-dev`，`KEEP_DEV_PARALLEL_LIVE` 是有效且正常的結果。

## 16.1 ResearchContext acceptance semantics（Pilot Evolution）

未來 ResearchContext／Market Regime／Private Research State／MCP implementation 的最小
acceptance 為：所有區段 same-`analysis_as_of` consistency、PIT 無 future leakage、相同
snapshot／revision deterministic replay、provenance present、stale／missing／partial explicit、
owner A／B isolation、bounded records／bytes／dates、無 secret／credential／storage locator
leakage、無 private-user mixing，且無 LLM-generated canonical numeric result。MCP 另須
negative-test arbitrary SQL／URI／owner injection 與 private-data leakage。

這些是能力 acceptance；其中與目前個人 live path 直接相關的部分以 real dev evidence 為主，fixture 只補異常情境。Supply-chain acceptance 仍依 Gate A–E，且 research-only/canonical/source authorization 邊界不因平行上線政策而改變。
