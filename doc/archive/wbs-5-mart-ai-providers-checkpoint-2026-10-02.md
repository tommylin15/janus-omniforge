# WBS-5-MART-AI-PROVIDERS checkpoint（2026-10-02）

整體仍為 **partial**。Codex 在既有 GCP dev Job 已能完成受控五角色執行；
第二批五份輸出均通過 validator，但分析結果均為 `insufficient_data`，不等於完整研究或每日自然批次已可用。

## 修改與驗證

- Code commit `2d240985d9f6f5a61f2e32e82ea22dd3206ba704`。
- OpenRouter 預設 `MART_OPENROUTER_FREE_ROUTE_CONFIRMED=false`，尚未驗收免費請求前不進 effective route。
  請求限定 prompt／completion `max_price=0`；費用缺失、非有限或負數保持 unknown 並 blocked；
  非零費用 blocked；以上失敗不 retry／fallback。Response 的 actual model 必須可觀察。
- Execution 固定 routing/profile/參數/effective providers snapshot 與 hash；interpretation 保存實際模型與參數。
- Codex 十次驗收入口禁止 OpenRouter／Gemini fallback，skipped audit entries 不計實際 invocation。
- 本機 targeted tests：**134 passed，3 Linux process tests deselected**。
- Canonical Linux CI [36991349892](https://github.com/tommylin15/janus-omniforge/actions/runs/36991349892)：
  **137 passed**，Mart deploy／verify success。
- [Provider routing CI 36991349896](https://github.com/tommylin15/janus-omniforge/actions/runs/36991349896) success。
- Dev image digest：`sha256:333c2bce3b50e821351ac00f4f23d75e8d718ef57c751729bb601051ae15d5a4`；Ready=True。
- Commit／push 前已執行 `/ponytail-review`；去除重複 artifact hash 計算，最終無剩餘精簡項目。

## 兩個 cold-start executions

兩批固定同一 source input，SHA-256：
`9e054d960a3f69242cc212684d081cd6109942d7a8696b638dfa52d6b68b3b73`。
Input：`gs://gen-lang-client-0593591102-dev-mart/acceptance/ai-providers/inputs/71db43bc-7fd3-46dd-a740-ab58a4fd81ba.json`。
`analysis_as_of=2026-10-01`，target count=3，admitted symbol=`2327`，deferred=2。

| 項目 | 第一批 | 第二批 |
| --- | --- | --- |
| Cloud Run execution | `janus-intelligence-mart-pgmx8` | `janus-intelligence-mart-8vf6n` |
| AI execution ID | `8fae53aa-5275-4a18-9fb7-57fbfb211ec7` | `9bd601d0-d396-4aec-a507-7e850936c7b7` |
| Invocation budget used | 5 | 5 |
| Validator | 四角色 validated；Quant blocked | 五角色 validated |
| 分析結果 | 四角色 insufficient_data；Quant worker 啟動失敗 | 五角色 insufficient_data |
| Auth version | 1 → 1 | 1 → 1 |
| Rotation observed | 0 | 0 |
| Publication writes | 0 | 0 |

第一批 Quant failure reason 為 `codex_cli_unavailable`；其 failed interpretation 的 validator
errors 為 `invalid_interpretation_contract`，不能反向解讀成「成功的量化分析資料不足」。
第二批 Quant 成功，沒有再次觀察到該啟動失敗；仍無足夠證據宣稱已找到第一批啟動失敗根因。

第二批耗時 7m30.41s；GCP `Started` condition 記錄容器啟動 3m36.96s。
每批最多單股×五角色、一次/角色、task maxRetries=0；建立第二批後 canonical Job 已恢復 maxRetries=1。
各批獨立讀回 **19 objects** 的 hashes／execution／Core／scope lineage；同 execution replay 未追加呼叫。

第二批 manifest：
`gs://gen-lang-client-0593591102-dev-mart/executions/9bd601d0-d396-4aec-a507-7e850936c7b7/ai-provider-manifest.json`。
Effective route 僅 `codex_cli`，模型 `gpt-6.1-sol`、reasoning `low`；OpenRouter 與 Gemini 均 blocked。
Routing hash：`sha256:d4bfbada6a528f5700dc0841e2cd2941245a9512670f5c7d8baeabde3b01f05a`。

兩批都從 dedicated Secret version 1 成功冷啟動，沒有原始資格進 artifact。
但沒有真實 rotation、revocation／重新授權 evidence；**cold-start 成功不能冒充續期驗收**。
已核准十次 invocation 上限已用完；這是本次驗收的授權上限，不是帳號剩餘 quota。
自然 AI 批次保持關閉。

## 2327 缺資料明細

另以既有 GCP dev Job `janus-intelligence-mart-bndhp` 做零模型唯讀檢查，重用同一 source input、
Core snapshot 與正式 catalog／analysis 路徑，重建五份 Fact Pack，**五個 role hashes 全部與第二批 artifact 相符**。
`provider_calls=0`、`publication_writes=0`，Job success。沒有追加驗收模型額度。

先前 Windows StaticTable 舊 metadata 路徑重建未與第一批 hash 相符，未採作驗收證據；
其差異原因未確認。本次缺值事實採上述 GCP 正式讀路徑的相符結果。
第一個零模型臨時 Job `janus-intelligence-mart-x7cp5` 因 Windows `.cmd` 改寫多行參數造成
SyntaxError，兩個 task attempts 都在讀資料前退出；改成單行 base64 source code 傳送後重驗通過。
Base64 內容只有程式碼，不含資格。這個失敗不計模型呼叫，也不列為成功。

### GCP Fact Pack 確認的七個 null

| 角色 | 實際 null | 同快照可用內容／限制 |
| --- | --- | --- |
| Fundamental | `revenue_trend_percent`、`eps_trend_percent` | 28 筆合格財報 observations、18 個有值 metrics，但 history 僅 **2026 Q2**；不足以提供跨期營收／EPS 趨勢。這是此 as-of pack 的覆蓋，不代表整個 DB 完全沒有其他財報 |
| Valuation | `roe`、`debt_to_equity` | PE=40.54、PB=7、殖利率=1% 已有值；缺 ROE 與負債權益比所需的合格輸入／指標 |
| Positioning | **沒有 null** | 八個淨買賣超／量能比彙總欄位都有值；insufficient_data 來自以下輸入說明／類別拆解需求 |
| Quant | `return_60d`、`return_120d` | 21 筆 OHLCV；完整 60／120 交易日報酬通常需 61／121 筆有效收盤價。20 日報酬已有值。其他目前已計算的量化欄位不代表具有完整 120 日價格歷史 |
| Event Risk | `max_severity` | 事件 dataset 可用且有 **5 筆事件**；未取得可用嚴重度評分／對應，不能把 null 當成零風險或解讀成沒有事件 |

同次分析的 345 筆合格 evidence 中，340 筆缺 `published_at`，317 筆缺 `availability_at`。
這是 provenance 欄位的觀察；received／record time 不能冒充官方權威發布時間。

### 分析師額外列出的研究資訊缺口

以下來自第二批 immutable interpretation 的 `missing_information`。
Validator 合格表示 schema／lineage／grounding 等檢查通過，不代表每句額外缺資料描述都已證明為 source-level 缺口。

| 角色 | 輸出列出的欄位／資料缺口 | 分析影響 |
| --- | --- | --- |
| Fundamental | `revenue_trend_percent`、`eps_trend_percent`；完整 12 個月營收、12 季財報；一般業／金融業分類依據；單季／累計口徑；現金流量與資產負債資料；權威 `published_at` | 不能提供完整營收／獲利趨勢、獲利品質與財務持續性結論 |
| Valuation | `roe`、`debt_to_equity`；適用同業估值比較基準；歷史 valuation observation 的指標名稱；PB 與殖利率的明確 evidence 對應及比較基準 | 無法完成相對估值與財務風險比較；不是 PE/PB/殖利率全部沒有數值 |
| Positioning | 各期間按投資人類別拆分的正規化結果；量能正規化分母定義與原始基準；獨立來源交叉驗證 | 現有籌碼彙總不能支持完整類別拆解與交叉驗證 |
| Quant | `return_60d`、`return_120d` | 缺乏足夠長期報酬比較；本批已成功執行，不再是第一批的 worker failure |
| Event Risk | `max_severity` | 無法以該欄位支持完整事件嚴重度結論；null 不可補成零風險 |

Fundamental 另外列出以下 raw 財報欄位未提供有效值：

- 停業單位損益、其他收益及費損淨額。
- 原始認列生物資產及農產品之利益（損失）。
- 生物資產當期公允價值減出售成本之變動利益（損失）。
- 已實現銷貨（損）益、未實現銷貨（損）益。
- 合併前非屬共同控制股權損益、合併前非屬共同控制股權綜合損益淨額。
- 淨利（淨損）歸屬於共同控制下前手權益。
- 綜合損益總額歸屬於共同控制下前手權益。

這些特殊會計項目可能不適用；不能只因模型列出 null，就要求補成數字或宣稱資料來源故障。
第一批另列 evidence 的 `availability_at`／權威發布時間與連續交易日覆蓋不足；須與實際 Fact Pack／provenance 核對。

完整財報歷史回補、新聞／外部研究來源等目前仍依 parking-lot／source authorization 邊界處理；
本 checkpoint 不把模型的額外研究需求自動轉成 active TODO。

## 未完成 gate

1. OpenRouter actual `$0` request acceptance 尚未執行；Gemini key 的 project Free Tier／billing 尚未證實。
   本回合的 operator probe 被自動審核拒絕：認為讀取這兩個 provider keys 並送往其外部 API
   尚缺 credential／destination 的具體明確授權。沒有改以 CI、Job 或其他途徑繞過此拒絕。
2. Auth 真實 rotation／續期、revocation／重新授權仍未驗收。
3. 全 target／情境的整體 acceptance 與持續批次額度尚未完成；單股 bounded acceptance 不等於全部聯集完成。
4. 五份 validated／insufficient_data 輸出不等於完整研究成功；不得放寬 validator、補算 missing facts 或借 fallback 隱藏資料不足。
