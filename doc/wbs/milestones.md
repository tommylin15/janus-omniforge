# Janus WBS — 建議里程碑

更新：2026-10-03
狀態：規劃索引；**active 執行順序只以 `../todo.md` 為準**

本文件只提供高階 milestone grouping，不建立第二套 TODO，也不保存已被取代的五 LLM roles／CIO／legacy Admin migration roadmap。

## 目前里程碑

| 里程碑 | 範圍 | 完成定義 |
|---|---|---|
| M0 | 基礎雲端／monorepo／CI/CD／IaC | 已有可運作的 dev workspace、repo、build/deploy 基礎；歷史完成證據查 archive／operations |
| M1 | Ingestion／Stage／Core／資料補強 | 約 500 market coverage、Core snapshots、12Q／12M／price history、daily incremental、Saturday DQ 與可重跑資料鏈完成對應 acceptance |
| M2 | Token-first specialist engines | 500 screening + Deep Coverage 五 specialist、PIT/OOS、immutable artifact、plain-language 0-token path、真實 dev execution/readback 完成 |
| M2.5 | Dirty dependency／model lifecycle | input-change invalidation、reuse、monthly retrain/calibration/reconciliation、champion promotion evidence 完成 |
| M3 | On-demand CEO | authorized manual command、provider route/auth/fallback、immutable report、quota/cooldown、usage/cost/audit、User read/action path 完成 |
| M3.5 | Admin operational convergence | 既有 Flutter Admin 的總覽／批次精簡強化、資料治理頁、AI Analysis Profile/capability，完成 authenticated dev browser + telemetry acceptance |
| M4 | User operational convergence | Stock Detail specialists/CEO/freshness/history、quote/portfolio/journal/workspace 既定契約與 real-path acceptance 完成 |
| M4.5 | User Final Visual Convergence | Today／Watchlist／Ledger／Stock Detail final visual contract、golden/screenshot、真實 dev authenticated browser acceptance 完成 |
| M5 | 長期 evidence／optional Production planning | 持續累積 Data／Analysis／Operations／Cost／Security evidence；只有真的有多人／對外／HA／SLA 需求時才進 Production planning |

## 現行 dependency 概觀

```text
Retention governance live acceptance
        ↓
Token-first specialist engines
        ↓
Dirty dependency / model lifecycle
        ↓
On-demand CEO provider + CEO Analysis
        ↓
Admin Analysis Profile / capability
        ↓
Admin operational convergence
        ↓
User operational convergence
        ↓
User final visual convergence
```

這只是對 `todo.md` 的視覺摘要；TODO 若調整順序，本圖隨之更新，不得反過來以 milestone 阻擋 active TODO。

## Admin 里程碑邊界

Admin 不再有 legacy static migration milestone。2026-10-02 起 Flutter／PWA 是唯一 active Admin frontend。

Admin operational convergence 不重做 shell：

- 保留 `總覽`、`批次`、`個股`、`市場資訊`、`AI 分析`；
- 原 `進階管理` 目標收斂為 `資料治理`；
- 批次使用簡單表格／清單，不要求大型 DAG；
- 資料治理單頁顯示 retention／DQ／storage／maintenance anomaly；
- 不引入第二套 scheduler、metadata platform 或 canonical store。

## AI 里程碑邊界

五 specialist：Python／SQL／ML；約 500 screening，Deep Coverage 才做完整五 specialist；dirty dependency incremental update；normal prose 0 API token。

On-demand CEO：只有 authorized manual request；`Codex CLI → OpenRouter → Gemini` 只屬 CEO／approved escalation route；重新分析建立新 immutable report。

任何舊「每日五 LLM analyst」、「CIO daily synthesis」、「single-role LLM rerun 自動 CIO」或「Pilot M1–M6 provider rollout」均已移出 active roadmap；歷史依 archive／Git history 查閱。

## Evidence window

長期 evidence window 不是使用資格 gate。已通過自身 real-path acceptance 的 capability 可直接在 dev 真實使用。

Evidence 至少觀察：

- Data：freshness、coverage、schema drift、quarantine、source reliability；
- Specialist：PIT/OOS、replay、model/evaluation、outcome；
- CEO：manual availability、provider/fallback、latency、usage/cost、usefulness（完成後）；
- Operations：batch/controller、maintenance、storage growth、failure/retry；
- Security/Privacy：auth、owner isolation、secret、delete/cleanup；
- Cost：Cloud Billing 與 provider/resource growth。

Production 是未來可選的多人／HA／SLA 營運層級，不是 M0–M4.5 在 dev 完成的前置條件。