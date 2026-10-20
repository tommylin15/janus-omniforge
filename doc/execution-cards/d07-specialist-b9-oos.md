# D07｜五分析師建模、OOS 與正式介接唯一 AI 任務卡

更新：2026-10-20。唯一狀態依 [TODO](../todo.md)；研究資料入口以 [GAS／Drive／Colab](../spec/research-collection-gas-drive-colab.md) 為準。此卡不再要求 Core frozen export、B5–B8 中轉、BQ SQL、Cloud Run monthly retrain 或 FINOPS-C 作為開工前提；過往 B9 證據只作研究比較。

## 1. 第一階段：新研究資料
1. 從 `janusChatGPT/資料源/YYYY-MM.zip`、manifest、quality 資訊讀取第三方合法採得的公開資料，TWSE/TPEx 普通股分開核對 ≥70%，排除 ETF 等其他證券。
2. 先用現行持股/觀察股公開欄位確認可取得內容，再延伸全市場。Quant：OHLCV、量額、基準、法人；Risk：價格及指數；Valuation：PE/PB/殖利率與財務；Fundamental：營收/EPS/淨利/財務比率；Event：公告內容/類型/來源。缺欄位保留 null/unavailable。
3. 來源時間欄位可貼標，**採集階段不以 PIT 版次/24 月完整歷史回補當阻擋**；不可冒稱以前即可取得。資料研究分母 70% 不可用作正式模型品質 PASS。

## 2. Colab 模型與驗收
4. Quant／Risk 優先建立 deterministic 與 LightGBM/statistical challenger；Valuation／Fundamental 依實際欄位與樣本；Event 未有真人標註及適用授權時維持 parser/rules。不得為五模型同時完成而硬填缺值或製造標籤。
5. 免費 Colab 由人工執行訓練及 OOS，固定版本／seed、訓練資料 hash、成熟標籤、時間外 walk-forward、purge/holdout、成本與風險評估；模型已 fit 不等於有效。因子可得性、模型 validity、正式 publication 分開。
6. 以可重現的 immutable evaluation/model/hash 導入 Janus Mart，只用於受控驗證、registry、rollback、推論／報告；正式服務不得改用 Drive 資料當 canonical number，不在 BigQuery／Cloud Run 建第二模型訓練器。

## 3. 退役及保留
- **舊 `specialist-retrain` Controller 月度派送、手動 workflow/request 與專屬舊研究 ML/OOS BQ 路線已退役，2026-10-20 實機驗收 `CLOSED`。** 詳見 [唯一結案收據](../archive/d07-gcp-bq-retirement-live-2026-10-20.md)；不為無異常證據的未知排程或資源重開工項。沒有研究相依的共用正式服務繼續保留。
- 保留現役正式 Core／Mart、TWSE/TPEx 正式品質 Gate、Owner/Portfolio、Market Screening、API、Stage 48h、Iceberg 週維護及備份。個人持有 ETF 仍能在持股頁顯示，但研究訓練母體不能包含 ETF。
- 本工項不新增付費 API、GCP 資源、擴權或刪除任何尚有正式引用的 canonical、private、已核准保護資料。個人非商業研究仍遵守資料來源存取、模型訓練與存放條款。

## 4. 每次執行必須回報
最新 GitHub main SHA、改動檔案、GAS 實際來源/月份/合格率、Drive 月檔 checksum、Colab OOS、各角色相對 baseline、Janus inference/readback、退役 GCP/BQ 資源 ID、測試 CI/live 工作與回滾。各子項 `DOC_UPDATED`／`COLLECTED`／`TRAINED`／`OOS_VALIDATED`／`PROMOTED`／`RUNTIME_REMOVED` 獨立判定，不把部分成功寫成全部完成。
