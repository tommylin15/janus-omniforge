# 四模型正式服務與研究生命週期

> 2026-10-25最新決策：Quant／Risk／Fundamental／Valuation本版全部正式上線，依[SEQ-06／08](../execution-cards/sequential-delivery.md)接線／驗收／發布；共用快取本版完成，不等待再次訓練。下文歷史研究、試訓、月評估及第五角色敘述不構成當前任務，研究調校／全面資料改善延至[2027 Q1第二版](../parking-lot.md#v2-2027-q1)。實際artifact／Registry仍以證據判定，不因規劃改判ACTIVE。

> 2026-10-24 批次與快照改以 [統一流程](unified-batch-flow.md) 為準。四模型按可發布規劃，既有artifact/Registry真實狀態不改判；訓練仍外部執行、無週月例行模型稽核、無GitHub業務cron。本輪未測試／部署。

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。

更新：2026-10-23。原模型生命週期與 Colab 規格保留，新增 ChatGPT 三角色試訓與四角色跨 Job 快取的延後整併決策。
**本文件是開發/營運目標，非已部署能力或已實收資料。** 模型/X/Y見[Specialist](specialist-engines.md)，精確時間/公式見[Feature契約](model-feature-time-contract.md)；不複製另一套公式。狀態唯一見[TODO](../todo.md)，操作與AI指令見[完整開發卡](../archive/document-cleanup-2026-10-25/execution-cards/d07-model-lifecycle.md)。

**本輪交付決策（2026-10-22）**：前四角色各自獨立 XGBoost Notebook；共用 Python 模組，不共用一份必須依序執行的訓練 Notebook。操作／AI 指令：[Quant 趨勢](../colab-models/01-quant-xgboost.md)、[Risk 風險](../colab-models/02-risk-xgboost.md)、[Fundamental 營運](../colab-models/03-fundamental-xgboost.md)、[Valuation 估值](../colab-models/04-valuation-xgboost.md)。Event 暫另議。本次僅文件完成，訓練與發布狀態仍依 TODO／實際收據。

### 2026-10-23｜Quant Q1–Q3 因子／切片研究結果（僅研究狀態）

- **已完成 `RESEARCH_EVALUATED`，未 promotion**：以 Stage 05.1／06 固定 Quant X/Y（807,948 原始列、473,378 筆合格模型樣本；X SHA `1b5c2cdd6f7b48427f81351ece2a855f4b97d44d89606ecd0f3fe29f5f8403ae`、Y SHA `e00b92ee1eb0d651b4baa5c28c2fa81dc9de6679b7e3e1b37a9a6ce1d1f44d5e`），執行 Q1 缺值與因子相關性、Q2 訓練期卡方／互資訊／每日 Spearman IC／Permutation、Q3 Logistic 固定參數的兩折成熟標籤 Purge 時間切片。這是與另份 Quant v3.6 真資料 OOS 收據**不同的研究 release/cohort**，不得混算績效。
- **候選不是決策**：同 15 因子共同樣本 95,751 驗證列／56 交易日期群，F1 15 因子 Brier 0.251413；F14 排除 `ret60`、`ret120`、`ret20_market_rank` 後 12 因子 Brier 0.250311，但兩折平均 AUC 0.5333 低於 F1 0.5359。F14 native cohort Brier 0.255715，劣於同 cohort 盛行率基準 0.251595；20 日 moving-block bootstrap 95% CI 跨 0，僅為候選研究訊號。保持 F1 基準與 F14 Challenger，**不永久刪正式因子、不換模型、不寫 Registry/ACTIVE**。
- **明確限制**：`ret20_market_rank` 橫截歷史母體 PIT、survivorship 與金融／非金融歷史有效會員資料未經驗證；Chi-square p-value 不代表獨立 OOS；2026-07/08 歷史測試曾檢視，不作本輪因子選組依據。Q4 前先診斷擴大早期 cohort 導致的績效退化；Q4 超參數／多模型調校仍未執行，且不因本研究自動納入 active TODO。
- **證據入口**：[GitHub Quant Q1–Q3 研究收據](../../research/experiments/quant-q123-20261023.md)；[Drive 研究報告](https://drive.google.com/file/d/1jZJwnTrQQ8gwgIzvdYDo0Rpgx2uSxODy/view)；[Drive 成果包（程式、CSV、manifest）](https://drive.google.com/file/d/1p6ZvCU_kXgWvLmHXaM3jGIc0bAz1yp4f/view)。來源訓練發佈權、獨立 forward OOS、校準、train/serving parity 及 dev promotion 均未經本次驗收，保持 `publication_allowed=false`。
### 2026-10-23｜三模型 ChatGPT 試做與四模型跨 Job 快取決策

**最新決策，覆蓋本文件較早的 Colab-only 步驟**：Drive `janusChatGPT/CoLab程式` 已有 `01_Quant趨勢_XGBoost.ipynb`、`03_Fundamental營運_XGBoost.ipynb`、`04_Valuation估值_XGBoost.ipynb`。三模型優先在 ChatGPT 可用 Python／研究執行環境試做，**不必使用 Colab**；Colab 保留選配。Notebook 存在與資料 `training_ready=True` 只表示可以試訓，不代表真實訓練、OOS、部署或 ACTIVE 已通過。Risk v1 的原模型/hash、現役發布與回滾狀態不因新試訓而改變。

1. **三角色先個別完成研究試訓**：固定讀取 `JanusDataset_v3_202610/canonical/CURRENT.json` 指向的不可變 Parquet release；核對 manifest、完整分區檔 SHA256、schema、時間、來源及使用授權。ChatGPT 環境若無 Google Drive 掛載，須經既有已授權檔案通道取得完整檔案，不能用文字片段/舊 r1 CSV/fixture 代替真實訓練。禁止重新採集已收資料。沿用各 Notebook 的 X/Y、label mature-at、PIT、公司行動、按時序切分與 purge、train-only 處理、baseline、OOS 與重載測試。記錄環境/依賴/seed/source hash/run fingerprint；預設 RESEARCH_ONLY、publication_allowed=false。
2. **可部署條件按角色獨立判定**：Quant（20交易日 p_up）、Fundamental（下一月營收 YoY）、Valuation（獨立 logPE/logPB）各需真實可重現 OOS/baseline、來源用途與時間合法性、必要污染控制、train/serving parity、模型 UBJ/前處理/schema/固定向量和 SHA、既有 GCS 不可變候選讀回、受控 shadow、registry/PG/API/UI/rollback 相容方案以及對應 CI/dev 證據。資料不足者保留 RESEARCH_ONLY/INCONCLUSIVE/BLOCKED，不能為湊齊三份而冒稱 DEPLOYABLE。
3. **三角色全部可佈版後才整併快取**：僅當 Quant/Fundamental/Valuation **全數具備可部署證據與受控發版入口**，才連同 Risk v1 一次改造共同 loader、版本釘選、快取與 registry，沿用既有 Scheduler→Controller→janus-intelligence-mart；不得提前改 Risk v1 現役推論、重新訓練 Risk 或另建每模型 Job。GCS 私有不可變模型與 manifest/hash 保留為唯一版本權威；按 role、model SHA、feature/preprocessor schema identity，Job 每次 execution 對每角色只載入一次到該 execution 記憶體，再批次向量化預測。
4. **跨 Job 快取並非共享 RAM**：不同 Cloud Run Job execution 不能保證保留前次 RAM、容器或 /tmp。先比較 A) 既有 GCS immutable artifact、每次 execution 單次下載+SHA驗證+in-process cache（低成本基線），B) 經 CI 綁定 image digest/model hash 的 image layer 內封裝模型（若實測較快且版本/回滾可控），C) 其他**已核准、成本確認**的共享快取方案。不得把 GCS 本身或容器暫存誤稱跨 execution 共享記憶體，也不新增 Redis/Vertex Endpoint/VM/常駐服務或付費額度，除非先取得使用者授權。
5. **統一驗收與回退**：同 target union、Core snapshot、as-of、X、版本下，比較改造前後模型讀取時間、load/predict/批次總耗時、GCS GET/bytes、CPU/RAM 峰值、成本估算；要求 fixed vectors、實際 dev 日批結果一致，驗壞 hash、cache invalidation、並發、Owner 隔離、ETF N/A、rollback。效益不明顯就維持 GCS+每Job單次載入基線；完成原定驗收才結案，不因假設性風險無限延長。

執行步驟與 AI 指令見 [D07 模型生命週期卡](../archive/document-cleanup-2026-10-25/execution-cards/d07-model-lifecycle.md)；三個角色的具體公式仍以各自模型文件為準。本項在原 D07 內，不另開 WBS 或增加 D08 工作。

## 1. 現況、架構與責任
以下早期基線保留作背景；新訓練輸入以 `JanusDataset_v3_202610/canonical/CURRENT.json` 指定 Parquet release 為準，Risk 既有 XGBoost8 參照專用模型卡／重訓手冊。早期查證基準 main 530a93030f478a91b33256ce98be6e55115a779c：
- 現有Colab採集README只示範2025-01～2026-09，共21個月，不是已收齊兩年，更不是五年。真實收量須讀manifest，不能由命令範圍推定。
- 已有 OHLCV 採集/月資料夾/續跑與 Risk 試點；Drive 三份 Quant/Fundamental/Valuation Notebook 已存在，仍需逐角色真實試訓及 OOS；共用 train/serving 前處理、其餘候選匯入、shadow、月評估與快取整併依 D07 的實際證據判定。
- Controller程式已有平日mart 09:00 due、market-screening 16:30 due，總控以每小時:30喚醒。09:00 due實際可能09:30才執行，**不能拿現有mart時段宣稱盤前報告已成立**。
- GCS只保存模型/小型事實/預測/報告；Cloud Scheduler→既有Controller→janus-intelligence-mart執行推論/結果回收。新三角色可於 ChatGPT 可用 Python 執行環境試訓，Colab 為可選替代；Notebook/Drive不是無人值守正式 runtime。
- Colab上傳是**模型業務artifact**，不改GitHub Actions→GHCR的程式Release路徑，不把GCS當container registry、CI receipt或release mutex。
- 程式與模型分開發布：新runtime/feature/schema先經既有GitHub CI/dev release；相容模型包才走registry promotion，不由Colab改Cloud Run image或正式active pointer。

## 2. 建議資料量（研究規劃目標，不是保證有效或統一硬門檻）
以歷史當時合格上市/上櫃普通股為母體；2026-10-21核定研究准入 TWSE普通股≥90%／TPEx普通股≥70%（現行名冊 PROBE 與正式PIT認證分開），各市場×dataset×月份獨立核對。個股IPO/資料短可用有值的事實，不要求每檔都存在五年。
| 角色 | 可開始試點 | 建議成熟研究資料量 | 建議模型窗口/評估 | 不足時怎麼做 |
|---|---|---|---|---|
| Risk | 18–24月日行情，扣warmup/未成熟標籤後做Ridge試點 | 3–5年日行情/指數/公司行動，約750–1,250交易日/長期存續股 | 常用近3年訓練，較早與多空階段作穩健性比較；最終6月holdout目標 | 先歷史波動/回撤與研究Ridge，不發布尾端機率 |
| Quant | 24月日價量可研究；現有21月仍可PROBE | 5年為主，3年可先做有界候選；約750–1,250交易日，法人/產業按有據期間 | 近3年或擴張窗比較，3月步進walk-forward；保留最近6–12月最終OOS目標 | 只用可用價量特徵，法人缺就不用；不把短樣本命中率當穩定勝率 |
| Fundamental | 36月營收或12季可比財報作簡單pooled試點；扣同比warmup後更少 | 月營收60–84月、財報20–28季（5–7年），含首次公布/修訂口徑 | 36–60月或16–20季train、6–12月或2–4季validation、最後12月或4季test；按實際總量調整 | 月模型可先行，季模型不足保留成長/品質規則；不能每天複製同季擴大樣本 |
| Valuation | 兩年有效PE/PB可做自身位置與同業規則 | 3–5年每日估值、12–20季相容財務/產業；研究抽36–60個月末截面 | 同業cohort/時間外倍數擬合；60/120日報酬效用另等標籤成熟 | 不足不產模型合理價；顯真實倍數與實際窗口 |
| Event | 規則不需要訓練標籤；分類試點約1,000個去重人審事件 | 約3,000–5,000個獨立事件、涵蓋24–36月；常見類別目標≥300，train/val/test各有代表性 | 依時間/事件家族分組，稀有重要類目標另累積100–200件，仍須不確定性評估 | 稀有類別不足沿規則/人工，不用過採樣假裝新增真事件 |
上述量為本專案建議起點，非統計保證。看學習曲線、有效獨立日期/季數、類別分布、分市場/產業表現再決定增量；不能以列數夠大取代時間證據。IPO/退市/停牌/修訂保留，不只收現今存活股。
初期先把可用既有21月Risk流程跑通；目標歷史分階段擴充，不為等五年而擋方案A事實產品。要延伸2025以前，先補對應年度交易日曆/來源支援與歷史母體，不能只改start日期硬跑。
以N個合格股票估容量：日頻約N×交易日數、月營收N×月數、財報N×季數；多股票共用market/benchmark，勿逐股複製大型raw。實測壓縮bytes/row後報成本，不編造GCS/Drive用量或免費保證。

## 3. 研究訓練八階段開發流程（ChatGPT／Colab）
所有notebook採版本化Python共用模組，不把主要邏輯藏在未追蹤cell；固定Git SHA、依賴版本、seed。每階段寫Drive manifest/checkpoint，可重新連線續跑；不可使用保活繞過Colab限制。
| 階段 | 操作 | 產物與完成條件 |
|---|---|---|
| C1採集 | 依既有README掛Drive，官方API整市場按日期抓OHLCV；補benchmark/公司行動；依角色再接營收/財報/估值/法人/公告 | 每月資料夾raw/normalized/quality/manifest，來源hash/權利/成功失敗日期；只下載缺的日期/修訂 |
| C2清洗 | 去重、單位、日期/交易日、普通股歷史母體、公司行動、財報單季/累季/股數口徑 | cleaned資料及rejected理由；缺值不補0；歷史raw引用可重現 |
| C3時間整合/X | 依Feature契約as-of join與lookback，多股panel；所有low-frequency以available_at對齊 | feature schema、實際起訖/缺值/age、source refs/input hash；不帶Owner私有資料 |
| C4貼標/Y | 在未來資料成熟後計算Quant/Risk；財報等下一公告；Event人審；估值當期倍數另標目標 | labels、mature_at、label version；訓練只用cutoff前成熟標籤，無Y的最新列留推論 |
| C5訓練 | 前四角色各自baseline，再單一XGBoost challenger；日期分組/去重事件切分；preprocessor只fit train | model/preprocessor/依賴/設定與train manifest，未做test調參 |
| C6OOS | walk-forward、purge、validation選型/機率校準，locked test最後使用；跨市場/產業/流動性 | evaluation含baseline、樣本數/獨立期數/coverage/不確定性；候選不佳保留舊版 |
| C7封裝 | 依角色feature/label schema與runtime版本打包；固定sample X及預期predict作相容驗證 | immutable bundle及逐檔SHA256；模型卡/來源授權/品質限制 |
| C8上傳與候選 | 人工授權短期身分→GCS候選prefix，最後上傳manifest；正式worker驗證 | CANDIDATE_UPLOADED不等ACTIVE；候選hash/權限/readback/registry收據 |
新訓練只讀 `janusChatGPT/資料源/JanusDataset_v3_202610/canonical/CURRENT.json` 的固定 Parquet release；衍生特徵/標籤/模型結果寫 `janusChatGPT/模型研究/<role>/<run_id>/`。既有 Risk 封存週期不搬移、不覆蓋；新輸出目錄是交付規格，非聲稱已存在。資料缺口與建議量存run manifest，不另複製多份TODO。

## 4. 五角色各自訓練／發布差異
| 角色 | Colab特別工作 | 發布內容/正式重算條件 |
|---|---|---|
| Risk | vol20/60等現有X→未來20日RV；Rolling20／Ridge5／Ridge8對XGBoost8；擴充分位須另驗coverage | XGBoost8 UBJ＋八因子特徵版本；baseline另存安全JSON；每個新EOD重算 |
| Quant | 價量/市場/法人X；5/20日return/up/outperform各目標分開；交易成本效用另算 | 各horizon/target的模型與校準器，不能混成一個概率；每日新EOD |
| Fundamental | 月/季公告原生樣本、成長與品質X；下一月/季首次公告Y；季節性／ElasticNet baseline對XGBoost月模型 | 月模型/季模型分開；有新營收/財報/修訂才重算，同一財報不每日重訓 |
| Valuation | 正同業PE/PB、財務as-of，排除目標代數等價X；cohort中位數／Ridge／Huber對XGBoost log倍數模型 | 同業/產業schema、倍數模型；價格/估值日更新可重估，財務特徵快取；不以定價擬合證明可獲利 |
| Event | 人審指南、抽樣複標、一致性/類別分布；TF-IDF及分類器只fit train，事件家族不跨fold | 先版本化rules；classifier有合格資料才發布；新公告/修訂才重算，日期到期做狀態轉移 |
每個角色可以是rules而不是ML，版本同樣可追蹤。五角色不用同時成功；壞模型不得阻止其他有效事實/角色服務。

## 5. 研究執行環境→GCS→正式發布
擬定模型業務prefix使用**既有dev Mart bucket**，實作前讀回bucket/IAM/現有retention，不新增bucket或默認擴權：
gs://gen-lang-client-0593591102-dev-mart/models/candidates/<role>/<model_version>/
此prefix是新設計，現有Runtime未必支援。不得套用舊分析只留三代/90天的清理規則直接刪候選或有效評估證據。

必要bundle：
- model：可信來源、允許格式；線性模型可用JSON係數/scaler/feature order，XGBoost使用原生UBJ/JSON；TF-IDF需完整vocabulary/idf/normalization。禁止載入任意pickle/joblib或從模型包執行Python。
- feature_schema.json、preprocessing.json、label_schema.json、training_manifest.json、evaluation.json、model_card.json、test_vectors.json、dependencies/format version。
- bundle_manifest.json：檔名/size/hash、role/version/source Git SHA/runtime compatibility、來源授權、OOS狀態、資料窗口、prediction horizons。不含token/Owner/私人資料。
- manifest最後create-only寫入；同版本不得覆蓋。中斷只有不完整candidate，不進registry；重跑已存在同hash可重用，不同hash拒絕。

發布步驟：
1. Colab操作者取得既有已授權身分的短期憑證；不下載服務帳戶key、不貼token到命令/Drive/notebook輸出。候選上傳只需限定prefix的objects.create；讀回另需限定objects.get。權限不足列精確缺項，不自行加Owner/Editor。
2. 上傳到candidate，使用generation precondition/create-only與checksum，再讀回核hash。**上傳模型不是啟用模型。**
3. 既有Mart受控import模式讀候選manifest，驗角色/相容版本/allowlist/大小/hash/來源/成熟OOS/測試向量；所有必要gate通過才登記VALIDATED。
4. 在既有正式公開資料上shadow推論，與Colab同X輸出對值，核延遲/資源/缺值/跨股；不得因hash正確就接受不可信模型格式。
5. 首次上線可用有界真實shadow＋已有合格OOS；持續5/20日結果追蹤不作虛構已完成。後續challenger至少觀察一個20交易日成熟cohort再評估替換，急迫錯誤可直接回退。
6. 由既有授權受控Janus流程原子切registry active version；expected_previous/version compare-and-swap，留下前版與變更原因。Colab uploader不能改active pointer。跨角色一批報告鎖定同一manifest版本集，避免中途混版。
7. 正式首批readback：模型/特徵schema、symbol/cutoff/預測、模板報告、API/UI/Admin一致，失敗只回退該角色。無上一有效模型則退rules，不製造空白全頁。
8. 模型更新相容才可只切registry；不相容schema/runtime須先走GitHub CI→GHCR→dev rollout/migration再匯入。不是從Colab直接部署服務。

## 6. GCS如何每天／每週產出分析
GCS不運算。**唯一既有Scheduler→Controller→Mart Job→Core/PG讀取＋GCS模型→批次推論→GCS壓縮結果＋PG serving→API/UI**。
下面是待實作due計畫，不宣稱現行排程已改：
| 節奏 | 執行與依賴 | 輸出 |
|---|---|---|
| 每個交易日盤後 | 接既有16:30 screening同日EOD成功後，既有Mart同occurrence後續階段做深度推論；不要另派兩份相同工作 | 公開每股facts/predictions、變化狀態、盤後摘要 |
| 每個交易日盤前 | 建議08:30 due，既有Controller tick下派送；最近完整EOD＋截止前事件；不把09:00 mart當盤前 | 盤前觀察/條件/已知事件；價量無新資料不重算同一模型 |
| 來源晚到/Controller忙 | 依cutoff發布可用區塊及資料日；08:55仍未完成則保留最近版本明示未更新，不冒充準時 | 部分報告/缺失原因；有界重試，不增加獨立cron |
| 每週六 | 資料品質完成後既有Mart受控階段核missing/drift/成熟outcome/未完成重試，與23:30 Iceberg維護隔離 | 週摘要與資料/推論健康；不每週重訓五模型 |
| 每月首個週維護 | 上月結算cutoff固定；評估截至該cutoff已成熟資料，記月份冪等key | 月度evaluation、保留/觀察/降級/回退/建議人工重訓 |
盤前08:30與既有supplement/鎖可能競爭，A3實作必做一次實測，採source ready/cutoff降級，不承諾秒級準時；若現有總控無法滿足，不暗增喚醒頻率，回報具體延遲與最小調整方案。
不恢復specialist-retrain。月評估是輕量scoring，不在Cloud Run fit；研究操作者在 ChatGPT 可用環境（或選配 Colab）讀月評估後重訓候選。

## 7. 每股獨立還是全市場一起
- **訓練**：每角色的pooled panel由多股票共同學習；不同target/horizon可多個estimator，不等於每股一套模型。
- **正式推論**：全市場僅沿用低成本screening；五角色深度推論只對active watchlist∪effective holdings普通股去重後的公開symbol集合。ETF持股行情照常，五模型不套用ETF。
- **批次方式**：同一Mart execution按角色載入一次模型、批次讀共享benchmark/cohort，分chunk做vectorized predict；初始可用100–250股作量測起點，以CPU/RAM/DB/GCS證據調整，不預設新增task/VM。
- 每股各有獨立feature/prediction/status/report identity；一檔缺值不讓整批消失。chunk checkpoint、input hash、model version、cutoff組成冪等key，失敗只補缺。
- 同股票被多owner關注只算一次公開結果；私人組合/成本/股數透過owner scoped API疊加，不能放公開GCS報告。
- Fundamental/Event依資料變更dirty cache；Quant/Risk新交易日更新；Valuation可重用財務特徵，只更新價格相關部分。
- 不逐股建立Cloud Run Job、不五分析師各建服務、不一次載所有歷史到Web請求；GCS按日批量/按月壓縮，而不是每股每天五個小檔。
- 月評估正式報告的母體是實際served cohort；若要宣稱全市場模型效果，另使用固定、版本化研究evaluation cohort。不能以個人關注的選股偏差冒充全市場效用。

## 8. 分析有效期、結果成熟與保存是三回事
每筆預測產生即保存prediction_id、symbol/role/model/feature/label version、cutoff/issued_at、X或精確可重現小型feature row、horizon、benchmark、prediction、status、cohort、target_end/mature_at、來源hash。
| 角色 | 當前顯示有效性 | 結果何時可評分 | 月報如何處理 |
|---|---|---|---|
| Quant | 新cutoff產生新版就顯新版；原5/20日預測仍追蹤 | 第5/20交易日結果資料完成，另計成本後可交易結果 | 本月成熟cohort；本月新預測未成熟列pending |
| Risk | 每日新EOD更新，過期資料標stale | 20交易日實現波動；延伸回撤/分位同窗 | 誤差/區間coverage/尾部，保留重疊樣本依賴 |
| Fundamental | 最新公告/修訂前仍可作該期觀察，顯資料年齡 | 下一月營收/下一季EPS實際公布後，不是月曆月底 | 以公告成熟樣本評估；無新季報就不強造本月季模型分數 |
| Valuation | 價格/倍數更新後新版；舊情境保留 | 當期估值模型殘差即時可核；60/120交易日效用分開等成熟 | 短期擬合與長期效用分欄，不拿當月未成熟算失敗 |
| Event | 事件仍有效/修訂/結束；公告時間明示 | 類別/重要性等人審；價格反應另等5/20交易日 | 文本正確率與市場反應分開；後見漲跌不能倒改原語意標籤 |
horizon用市場交易日，非湊滿20筆有價觀測；停牌/退市導致終點無合法值，按事先label policy處理並列censored/pending，不能無限順延到有利價格。正式歷史預測不可被新版改寫；來源修訂新增outcome version。
每月同時看「本月成熟」「原發出月份cohort」「近3/6/12月滾動」，避免只看單月偶然好壞。

## 9. 保存與壓縮建議
本節為新模型回饋產物政策，實作前須加入既有retention保護/分類與有界讀回，不在本次文件更新執行刪除或加費用。
| 資料 | 建議保留 | 方式 |
|---|---|---|
| API熱讀分析/觀察 | 365日 | 最新索引PG、歷史小型facts；不把所有模型payload複製PG |
| 精簡預測＋實際結果＋必要X/cohort | 36個月，自issued_at起；未成熟/現役audit引用者到結束再清理 | GCS每月壓縮分區，daily bounded checkpoint月封存核hash後合併；保留restatement |
| 月度evaluation/模型卡/選型決策 | 36個月；現役/回退模型引用超過時保留至退役後12月或36月期限較晚者 | 小JSON/Parquet/manifest；無重複全量報告 |
| 模型包/前處理/必要訓練版本 | active＋前兩個有效回退版始終保護；其餘已發布版至少36月且覆蓋被保留預測引用 | 去重共用資料manifest；同資料不為每模型複存 |
| 未發布失敗candidate | 終態後90日（建議）；仍審核/被引用不刪 | 保留小型失敗摘要36月；實施需TTL保護驗收 |
| 研究raw/clean/月檔 | 按角色3–7年需求與來源保留權利；被有效訓練包引用者pin | Drive研究保存；不把全部研究raw複製GCS |
36月是回饋明細的成本/比較折衷，不是所有Core/Stage改三年。Stage48h、正式Core row/current snapshot、既有Mart90日/三代分析不被自動擴大；新feedback/model prefix需明確豁免錯誤套用舊TTL。若來源權利不允許目標保留期，採合法替代或縮短並記錄不可重現範圍，不能隱瞞。
不必保存每次整個原始行情窗口；保存當時X、小型source/version/hash及必要研究manifest即可。hash不能取代被刪掉的原始資料；嚴格重現所需訓練輸入仍須保留合法副本。

## 10. 每月評估與下一輪
1. 每日/週批只回收新成熟Y，不重算已固定結果；缺來源待補、修訂追加版本。以model_version分組，不能把新舊模型績效混為一條。
2. 月初固定cutoff，對本月成熟與3/6/12月滾動cohort計算各角色既定metrics、coverage、baseline差、資料缺失、drift、分市場/產業、延遲、費用/資源。
3. champion與shadow challenger必用同一可比較cohort、cutoff、label、成本假設；無足量成熟證據則INSUFFICIENT_MATURED_LABELS，不以0命中率或PASS代替。
4. 訓練前evaluation plan固定允許退化幅度/樣本下限/校準容忍，根據當時OOS與block uncertainty設定，不為所有角色硬訂「勝率60%」。不得看本月test後追改門檻。
5. 狀態：KEEP（維持）/WATCH（觀察）/RETRAIN_RECOMMENDED（回Colab）/ROLLBACK或RULES_ONLY（具體品質/相容錯誤）。安全/數字/模型相容錯誤立即停該角色；統計退化應以成熟樣本及不確定性證據判斷，非一個月負報酬自動重訓。
6. 研究操作者在 ChatGPT 執行環境（或選配 Colab）人工讀月評估，更新已到位資料、重建有版本X/Y、訓練新candidate；新增資料只用當時成熟label。看過的歷史OOS可成後續training，但不能再當新模型獨立test；保留新的時間外期間/前瞻shadow。
7. 新candidate→immutable上傳→validator→shadow→promotion/保留舊版，循環回每日推論。月評估自動產出不等自動重訓/自動替換模型。
8. 每月Admin只列每角色版本、有效樣本與成熟期、相對baseline、狀態/理由、建議動作；一般User只看可理解研究結果。

## 11. 交付與引用
交付狀態：沿用 `00_資料收集.ipynb`；Drive 已有 Quant/Fundamental/Valuation 三份獨立歷史 Notebook；Quant v3.6 回溯研究 OOS 與 Stage 05.1/06 Q1–Q3 研究比較均有獨立收據，但未完成正式獨立 OOS／可部署驗證，Fundamental/Valuation 仍依實際證據判定；Risk v1 沿用既有模型與專用發布管線；共用 Python 模組/資料標籤 builders、bundle exporter/uploader、Mart 匯入/registry/shadow、批次推論、outcome/monthly evaluator及必要 Admin 呈現各按實際版本/測試與 dev 驗收判定。Event 另議；本節是交付契約，不冒充未驗證的 runtime 能力。
官方參考（2026-10-21查閱）：[Cloud Storage上傳與generation precondition](https://docs.cloud.google.com/storage/docs/samples/storage-upload-file)、[Cloud Run Jobs排程](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule)。Google提供機制不等於本專案已配置，驗收依runtime readback。

