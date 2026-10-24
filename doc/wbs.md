# Janus — Work Breakdown Structure

更新：2026-10-24（跨線依賴矩陣）
狀態：索引；執行順序與未完成條件以 [TODO](todo.md) 為準

## AI 最小讀取規則

收到 WBS ID 時，先從 TODO 取得範圍與驗收，再只讀對應切片及其直接引用的 SPEC／UI 切片。每個 AI 一次只擁有明確工作包；跨工作線允許分人平行，但共享 Controller／Registry／release／canonical writer 必須互斥。2026-10-05 的 A／B／C 合併工作組依 PROJECT_RULES 例外，以指定整組執行、共用驗收，原 WBS acceptance 保留。只有使用者明確指定全部組才跨組連續執行；不在 dataset／檔案／畫面之間反覆停等。操作見 [Codex 執行指令](codex-execution-plan.md)，範圍與狀態仍只看 [TODO](todo.md)。

## Dev 平行上線驗收原則

- 目前 `dev` 是個人使用階段的真實平行上線環境；WBS 的主要驗收預設走實際 GCP dev URL、真實 OAuth、真實持久化資料、真實 API／MCP／provider 與既有 Job／Scheduler，而不是先以 mock／fixture／假資料取代。
- 本機 unit／contract／fixture 保留作快速回歸或故障注入；不得取代主要 real-path acceptance。
- Production 只代表未來對外、多使用者、HA／SLA 或更嚴格營運需求；除非 WBS 明確屬於該範圍，不能以尚未 productionize 阻擋目前 dev 真實使用。
- 程式已寫完但未部署、未觸發、未連真實依賴或只跑模擬資料，不得宣稱整體完成；partial success 不得包裝成 full success。
- secret redaction、owner/auth boundary、migration 可追蹤、重要資料可重建／備份、不可逆大量刪除防護，以及 research/canonical/PIT/provenance/source authorization 邊界仍有效。

## AI角色分工（非工具可用性閘門）

舊 Sol／Luna 是歷史分工註記，不是模型選擇或前置閘門。**新工程順序以TODO為準：A-CHANGE → D07-PRE → D07 → D08；STAGE獨立收尾**（見 [TODO](todo.md)）；下表 A／B／C、WBS3/4/5/6 的已結案範圍只用於找舊設計、修復所屬模組及稽核，不能成為另列的 backlog。工程依現有能力與 PROJECT_RULES 在 main 執行，不主動建 branch/PR。

## 多工作線協同 WBS／依賴路由（2026-10-24）

本表只定義**責任切片、SPEC、必要前置與合流 gate**，不複製進度；唯一 active 狀態與下一個可執行工項見 [TODO §1](todo.md#1-現行總優先順序與唯一主待辦2026-10-24-整併)，證據在 [Operations](spec/operations-and-testing.md)／相關 research receipt。AI 領取任務時先固定 `main` SHA、run_id、資料 release/fingerprint，再依直接依賴選擇最少必要文件。

| Lane／WBS 擁有者 | 必讀 SPEC（設計契約） | 上游與可以先做的平行工作 | 禁止跨越的 gate／合流 |
|---|---|---|---|
| **O／WBS-3+7+8：Controller／57 leases／backup** | [資料治理](spec/data-governance.md)、[Retention](spec/retention-governance.md)、[Controller runbook](runbook-batch-controller-dev.md) | P0-2 審計／逐筆 reconciliation 可與 P0-1 自然 occurrence 唯讀觀測及其他研究同時進行 | 同一 Controller release／queue mutation 一次只容一個 owner；先驗 artifact、lease/fence、digest/live；未驗終態不更新 |
| **G／WBS-3+7：C0-Live→C1-A 資料治理** | [資料治理](spec/data-governance.md)、[資料保存](spec/retention-governance.md)、[研究候選與 Live](research/data-governance-c1a-2026-10-23.md) | PG/Iceberg reader/lineage 盤點可與市場 preflight／模型研究平行；逐張決策 | **C1-B DROP/DELETE 不可由文件直接放行**；需確認 active readers、backup/rebuild、owner/publication、current snapshot、回復與有界 apply 驗收 |
| **D／WBS-3+5：研究採集、Preflight、X/Y** | [研究採集](spec/research-collection-gas-drive-colab.md)、[特徵時點](spec/model-feature-time-contract.md)、[最新版本索引](research/00-四模型最新版本索引.md)、[Preflight SOP](research/four-model-research-package-preflight-runbook.md) | 個股/市場產業收檔、查缺、PIT membership、欄位/單位 mapping 可按資料集分線；versioned release 彼此不覆蓋 | X/Y 依 frozen CURRENT/manifest/hash；產業 X 需真實歷史名冊與 crosswalk，Core/Stage writer 和清掃需避免競寫；研究資料不可默認 canonical |
| **P／WBS-5+6：A-CHANGE／Janus 2.0 UI** | [變化判讀](spec/change-analysis.md)、[UI](ui.md)、[2.0 Drive 報告](https://drive.google.com/file/d/15sT38MsE96RAwD-aZnAHvOvEINtythPO/view) | 先驗既有 A1–A4，UI 重要性排序／簡化摘要與 RV-01/02 可以並行；可不等 ML | 後端只產出一份 versions/facts；RV-05 合流後一致 API/Owner 授權／真實 UI，不能以視覺樣稿代替讀回 |
| **V／WBS-5+6：第五角色 RV-01…06** | [估值參考區間](spec/valuation-range.md)、[資料來源](spec/storage-data-and-ingestion.md)、[時間契約](spec/model-feature-time-contract.md) | RV-01 真實來源盤點、RV-02 純函式及 UI 設計可並行；**不依賴第04 Valuation XGB 可部署** | RV-03 真實可得/PIT → RV-04 相容 Mart/API → RV-05 一條價帶與 A-CHANGE 合流 → RV-06 dev/Owner/回滾驗收；不能冒稱 ML 預測 |
| **M-Q／WBS-5+8：Quant 獨立研究** | [Quant 角色](colab-models/01-quant-xgboost.md)、[生命週期](spec/model-lifecycle.md) | 研究凍結 r1、前瞻 cohort、成熟回收可和其他模型獨立作業 | baseline/獨立 OOS/校準不足不得發布；不覆蓋別人的 frozen artifacts |
| **M-R／WBS-5+8：Risk 現役＋研究** | [Risk model card](spec/risk-model-card.md)、[PROJECT_RULES §1.12](PROJECT_RULES.md#112-d07-risk-xgboost8-v1-正式-promotion-嚴格門檻2026-10-23-最新指令) | shadow/OOS 資料收集可與 Quant/Fundamental/Valuation 分線；正式日常 inference 維持原服務 | 嚴格來源/新成熟前瞻/獨立 OOS/PIT/action/parity/CAS/rollback 全 gate 才可切 ACTIVE；**現有 deterministic serving 不由研究者修改** |
| **M-F／WBS-5+8：Fundamental 獨立研究** | [Fundamental](colab-models/03-fundamental-xgboost.md)、[時間契約](spec/model-feature-time-contract.md) | 可凍結研究 RC1 並同步查可用公布日／Y；不等 Quant 完成 | CURRENT 真實 PIT、成熟標籤、OOS、serving parity；研究 PASS ≠ 發布 |
| **M-V／WBS-5+8：Valuation 第四角色研究** | [Valuation](colab-models/04-valuation-xgboost.md)、[Valuation 稽核](research/valuation-p0p1-live-audit-2026-10-24.md) | 財務單位/期間/mapping/PIT 品質與第05角色 EPS/BVPS 來源可共用**只讀核查**，各自定義輸出 | 第04的相對倍數模型 ≠ 第05的價格情境；資料不可比先 blocked，不能把兩套價格都當 canonical |
| **I／WBS-5+6+8：CEO/D08／整合發布** | [Intelligence](spec/intelligence-and-governance.md)、[D08 卡](execution-cards/d08-ceo-admin-owner-report.md)、[User UI](ui/user-app.md) | 事實 Pack、手動請求、validator、Owner history 可先做；不等待全部模型可部署 | 涉及模型結論僅讀該模型過 gate 的已發布 version；immutable report、auth、source、rollback 一致 |

### 依賴關係／可平行與互斥

```text
O-P0-2 審計 -> lease/artifact 安全分類 -> Controller live 驗收 -> 57 UUID 終態
O-P0-1 自然觀測 ------------------------------ (與 O-P0-2 唯讀並行)
G-C0 Live -> C1-A reader/rollback -> (另案批准+safe apply) C1-B
D-採集/缺口 -> frozen release + preflight -> [M-Q | M-R | M-F | M-V] 各自 OOS
V-RV01 ─┬→ RV03 真資料 ──┬→ RV04 API/Mart ─→ RV05 UI ─→ RV06 驗收
V-RV02 ─┘               ┘                       ↑
P-A1..A4/2.0 UI ────────────────────────────────┘
I-事實 Pack 可先行；每角色模型 publication gate → 該角色結果接 D08
```

**平行不等於同時改同一資源**：共享 `main` 調整以小 commit、重讀 HEAD 和不互相覆蓋為準；Controller/ingestion 改動必針對 deploy lease 序列化；GCS publication/Registry/PG migration/retention apply 需有明確單一責任與 rollback。研究四角色使用隔離 run_id、candidate、frozen X/Y fingerprint；任何模型試驗不得改 canonical 或現役 Risk；公開事實與 Owner 私人資料隔離。C1-B 清掃不可穿插未完成的資料/reader 合流。

**一次只維護一份 TODO**：此表的 `Lane` 與 `RV/OPS/GOV/DATA` 工作 ID 在 [TODO §1.1](todo.md) 找到唯一未完條目；驗收證據追加到指定 Operations/研究 receipt；完結後從 TODO 移出，摘要保留於 [結案索引](wbs/completed-index.md)，不創造分支 TODO。

## WBS 路由

| 任務／WBS | 預設模型 | 必讀切片 | 條件增讀 |
|---|---|---|---|
| D07-PRE：Colab 採集／ChatGPT 四模型貼標與產業歷史 PIT | 依當前能力 | [Active TODO D07-PRE](todo.md)、[研究採集契約](spec/research-collection-gas-drive-colab.md)、[兩入口與產業歸屬 preflight](research/four-model-collection-label-split-v382.md) | 只在需要時讀 [時間契約](spec/model-feature-time-contract.md)；程式交付與實際資料 PIT 分別驗收，不能把產業指數當逐股名冊 |
| A-CHANGE：站內變化判讀 | 依當前能力 | [方案A卡](execution-cards/a-change-analysis.md)、[契約](spec/change-analysis.md) | WBS-5/6增量；A1→A2→A3→A4整包驗收，不重開已結案D03 |
| A：User／Admin／效能／資料營運 | 【Sol】 | [執行指令 A](codex-execution-plan.md)、[WBS 6](wbs/wbs-6-api-and-apps.md)、[WBS 7](wbs/wbs-7-security-finops.md) | 私人資料讀 4J／4R；Core query／projection 讀相應 SPEC；User／Admin UI |
| B：specialist／cache | 【Sol】 | [執行指令 B](codex-execution-plan.md)、[Specialist Engines](wbs/wbs-5-specialist-engines.md)、[WBS 5](wbs/wbs-5-intelligence-mart.md) | 對應 runtime／retention／Admin 顯示 |
| C：CEO／profile／User 最終整合 | 【Sol】 | [執行指令 C](codex-execution-plan.md)、[WBS 5](wbs/wbs-5-intelligence-mart.md)、[WBS 6](wbs/wbs-6-api-and-apps.md) | API／auth／User／Admin UI；重用 A 未受改動的驗收 |
| 已完成證據定位 | 【Luna】 | [已完成工作](wbs/completed-index.md) | 只在需要歷史證據時讀 archive |
| 3：Ingestion／Core／Admin Data Operations | 【Sol】 | [WBS 3](wbs/wbs-3-ingestion-admin.md) | UI 變更再讀 Admin UI |
| `WBS-3-DATA-SUPPLEMENT-V1` | 【Sol】 | [補資料第一版](wbs/wbs-3-data-supplement-v1.md) | 已結案；維運依 runbook，不重開舊 minimum-floor 工作 |
| 4J：個人記帳、筆記、關注股 | 【Sol】 | [WBS 4J](wbs/wbs-4j-personal-workspace.md) | 外部助理只透過 Janus domain API／MCP 讀授權 context；曝險才讀 4R |
| 4C：Janus Chat／Agent（已退役） | 歷史 | [退役責任摘要](wbs/wbs-4c-ai-chat.md) | 不作 active execution；舊規劃只供 archive 查閱 |
| 4R：個人曝險、績效與壓力測試 | 【Sol】 | [WBS 4R](wbs/wbs-4r-personal-risk.md) | 若交由外部助理解釋，依 bounded context／MCP 契約 |
| 5：Intelligence Mart／Fact Pack／Token-first specialists／On-demand CEO | 【Sol】 | [WBS 5](wbs/wbs-5-intelligence-mart.md) | specialist 細節讀 [Specialist Engines](wbs/wbs-5-specialist-engines.md)；active slices 只看 TODO |
| 6：FastAPI、Flutter、Admin workspace、MCP | 依 TODO | [WBS 6](wbs/wbs-6-api-and-apps.md) | User 讀 User UI；Admin 讀 Admin UI；不預讀另一側 |
| 7：安全、監控、FinOps | 【Sol】 | [WBS 7](wbs/wbs-7-security-finops.md) | 依受影響服務增讀其 WBS |
| 8：PIT、QA、發布／evaluation | 依 TODO | [WBS 8](wbs/wbs-8-qa-release.md) | 需要現況證據時讀 status／operations；歷史 Pilot checkpoint 不覆蓋 active TODO |
| Research Context（Planned） | 【Sol】 | [WBS 3](wbs/wbs-3-ingestion-admin.md)、[4J](wbs/wbs-4j-personal-workspace.md)、[5](wbs/wbs-5-intelligence-mart.md)、[6](wbs/wbs-6-api-and-apps.md)、[8](wbs/wbs-8-qa-release.md) | 只在 active TODO 啟動後執行；不重開 WBS 4C |
| 里程碑規劃 | 索引 | [目前管理里程碑](wbs/milestones.md) | 不作單一 WBS 的驗收來源 |

任何歷史 WBS 名稱、舊 Pilot milestone 或 archive 內容若與 active TODO／SPEC 衝突，不得反向取得 active execution authority。
