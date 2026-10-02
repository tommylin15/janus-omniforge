# Janus — Parking Lot／暫不做

更新：2026-10-02

用途：保存目前**不做**、不計入專案未完成度、也不應阻塞 foreground／completion 的構想、未來可能需求與已接受缺口。

這不是 active backlog。只有使用者日後明確決定「要做」，項目才重新移回 [`todo.md`](todo.md) 並取得明確順序與 acceptance；不得因本文件存在就自行開工。

## 1. Pilot observation／Production 才需要的工作

以下不再以 active TODO checkbox 表示：

- `WBS-8-DEV-PILOT-RUN` 的六個月自然 Scheduler／ingestion／analysis、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure、security／privacy evidence。自然 evidence 仍由 [`pilot-operational-evidence.md`](pilot-operational-evidence.md) 保存，但沒有新事件時不製造人工工作。
- `WBS-8-PROD-GO-NOGO`。
- Production PostgreSQL topology／HA／replica／backup／retention／成本重設計。
- Production 付費 backup／restore 演練。
- Production 人工批准。
- 新 GCP service、HA／replica／multi-region／GKE 或只為架構整齊而新增的 infrastructure。

目前 `dev` 仍是個人使用階段的真實 parallel-live 環境；以上項目不構成目前功能未完成。

## 2. 已接受的資料缺口／完整歷史回補

目前不追求每個 dataset／symbol 100% 完整，也不把已通過 acceptance 的 source-level missing 永久掛在 TODO。

暫不做：

- 將 TWSE 500 各資料集追補到 500/500。
- 為了消除 `partial` 標籤而逐筆追補來源本身缺檔。
- 全市場／全標的完整財報歷史、12 月／12 季等歷史回補到「無缺口」。
- 既有 FinMind financials blocker 的替代接線，只為補齊 500/500 而新增來源。
- 離榜持股 future-feed 的全面 source expansion，只為消除歷史 `partial`。
- day-trading 等已在既定 coverage 門檻內的殘餘缺值逐筆追補。

既有 WBS-3 coverage acceptance 已依使用者核准門檻完成；後續五分析師遇到必要 evidence 缺失時保持 `missing_data`／`insufficient_data`，不得由五個角色各自重複抓資料或補造 canonical facts。若日後決定正式做共用 Evidence Gap Resolver／研究型補證據層，再明確移回 TODO。

## 3. 深度行情／外部研究來源擴張

暫不做：

- 分 K／Tick 全面收集與獨立排程。
- 新聞／券商研究／目標價資料源接線。
- social／Podcast／alternative-source adapter。
- 未核准來源的 executable adapter／排程。
- Yahoo Finance 在沒有明確授權前作 executable runtime source。
- 額外 AI role、非必要 analysis dashboard。

來源候選、授權狀態與技術研究可保留在規格／決策文件，但不因存在候選就形成 active TODO。

## 4. 個人化／文本與深度追蹤擴張

暫不做：

- 另建個人化公開 Mart analysis 流程，只為增加 individualized research depth。
- 通用文本正規化、dedup、language、published time、entity-to-symbol、source authority Core tables 的全面擴張。
- sentiment／buzz／AI alert 等額外 Mart 產品。
- 深度追蹤 demand 的進一步 cadence／retention expansion，超出目前 Watchlist／持股與既有研究需求者。

## 5. Pilot Mart AI evaluation 擴張

暫不做獨立 `WBS-8-PILOT-MART-AI-EVALUATION` active checklist。若目前 foreground `WBS-5-MART-AI-PROVIDERS`、CIO、rerun/cache 的 acceptance 已自然產生 provider failure、latency、quota、cost、manual intervention 等 evidence，可照實保存；不另為了「填 evaluation TODO」製造工作。

## 6. PIT／Outcome／治理校準

暫不做：

- PIT outcome／sample payload 額外 GCS／Iceberg productization。
- 5／20／60 交易日 outcome pipeline。
- relative benchmark、MFE／MAE、coverage evaluation。
- 額外 publication-time／provenance exclusion dataset，只為 calibration 而建立。
- weights／40-60 thresholds walk-forward。
- 正式 governance revision proposal，只因 roadmap 項目存在而提前產出。

## 7. 完整 device／A11y／release matrix

暫不做完整矩陣：

- Flutter Android／iOS／Web 全 phone／tablet／desktop breakpoint matrix。
- iOS Safari、Android Chrome、iPad Safari 全面矩陣。
- VoiceOver／TalkBack 全面 acceptance。
- WCAG AA 全產品矩陣。
- 全主要控制 44×44 專案級掃描。
- K 線 pan／zoom／tooltip／替代表格完整 accessibility package。
- 全 Dialog focus-trap／Escape／restore／scroll-lock 專案級掃描。

目前實際使用裝置或既定 final visual acceptance 中真正需要的相容性，應直接寫進對應 active WBS acceptance；不再用一長串泛化 checklist 掛在 TODO。

## 8. P4 資料品質校準擴張

暫不做整組 P4 roadmap：

- coverage-tier source health telemetry 全面擴張。
- 全套跨源一致性、null profile、freshness、coverage、schema drift、outlier、corporate-action DQ ruleset。
- market regime／sector rotation／topic uncertainty／candidate health／private PnL quality discount calibration。
- 獨立 Admin DQ dashboard／quarantine drill-down／quality revision diff。
- UI case regression set 專案化與 30% gate 重校。
- production-grade DQ revision proposal。

目前真正發生且會影響 correctness 的 DQ bug 仍可在其 active WBS 直接修，不需先把整套 P4 roadmap 復活。

## 9. Research Context Pilot Evolution roadmap

以下整組 roadmap 從 active TODO 移出；目前不做：

1. `WBS-3-DATASET-COVERAGE-INVENTORY`
2. `WBS-6-RESEARCH-CONTEXT-CONTRACT`
3. `WBS-4J-PRIVATE-RESEARCH-STATE-CONTRACT`
4. `WBS-5-RESEARCH-MART-CONTRACT`
5. `WBS-3-RESEARCH-DATASET-GAPS`
6. `WBS-6-RESEARCH-CONTEXT-COMPOSITION`
7. `WBS-6-RESEARCH-CONTEXT-UI`
8. `WBS-6-CHATGPT-MCP-RESEARCH-CONTEXT`
9. `WBS-5-SUPPLY-RESEARCH-CONTEXT`
10. `WBS-3-NEWS-ALTERNATIVE-SOURCE-REVIEW`

## 10. Supply-chain research planning

Supply-chain ontology、Source Matrix、seed graph、signal contract、Pilot measurement／epoch planning 保留在既有 WBS／SPEC 作研究材料，但目前不作 active TODO，也不得因此建立 production ingestion、schema／migration、crawler、未核准 adapter、paid source、tick／high-frequency source、Mart implementation 或新 GCP resource。

## 11. 明確不重開的範圍

- Janus 舊 WBS-4C Chat／Agent 通用 runtime。
- Janus 內建 Chat／Ask Janus／Skills／通用 provider selector。
- 為純 cosmetic polish 建立獨立工程 WBS。

需要上述任何項目時，先由使用者明確決定「做」，再從本文件搬回 `todo.md`；在那之前不視為欠債、不影響專案完成度。