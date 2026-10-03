# 補資料第一版 S0 evidence／決策入口

更新：2026-10-02。狀態：S0 partial／官方歷史證據查核中；使用者已採用 bounded TWSE／FinMind／MOPS 方案，S0／S1／S2 尚未完成。

使用者已指定優先執行 `WBS-3-DATA-SUPPLEMENT-V1`，Provider WBS 保持 partial。

## Pinned baseline

- `analysis_as_of=2026-10-01`；Core execution `f8f3b62d-6ba4-439a-b521-1899df308910`。
- Input SHA-256 `9e054d960a3f69242cc212684d081cd6109942d7a8696b638dfa52d6b68b3b73`。
- Core manifest SHA-256 `ad9e97531023b32ea206c2ef1f2e7a967ebfc39c0cd55a42844f4dd6206e51a6`。
- Core snapshot `sha256:dbac33d5af89ba57047ee499fbe9800dd2906d08c5b2662f2080522f8f3b44e5`。
- 唯讀 GCS input／manifest readback 成功；manifest 包含九張 Core tables。
- 四個 input symbols：`1102,2327,2330,4958`；這不等於目前全部 active AI targets。
- 原五角色 hash 相符證據見 [Provider checkpoint](archive/wbs-5-mart-ai-providers-checkpoint-2026-10-02.md)。

## 已查證的程式路徑

`storage.load_core_datasets` 讀 immutable manifest 指定的 snapshot，以 symbol 過濾，沒有把 history 裁成 21 天。`analysis._research_rows` 再以 financial availability fence 選 revision，`validate_evidence` 決定 qualified evidence。

| Requirement | 已知 baseline／實作根因 | 分類／下一個查核 |
|---|---|---|
| 60／120 日價格 | 2327 qualified OHLCV 21 筆；讀取函式未截短 history | `history_depth_gap`；核對 raw snapshot 與其他 targets |
| 12 季財報／trend | 2327 qualified financials 僅 2026 Q2；MOPS adapter 只接 `t187ap06_L_*` 損益表 | `history_depth_gap`；核對 raw periods，再評估官方歷史路徑 |
| 12 月營收 | 既有 adapter set 無 monthly-revenue；季報 revenue 不能充作月營收 | `source_gap`／尚需 bounded historical admission 查核 |
| 現金流／資產負債、ROE／D/E | 現行 MOPS 六個 endpoints 都是損益表；ROE 未 derive，D/E mapping 還包含不同語意的「負債比率」 | `metric_mapping_gap`＋input composition；需合格權益／負債／跨期獲利 |
| 一般／金融業分類與單季／累計 | normalizer 預設 statement=income，沒有保存所屬 endpoint 的業別／口徑 | `semantic_gap`；不得由 symbol 或公司名稱猜分類 |
| 同業估值基準 | 現行 valuation features 只取最新單股 PE/PB/yield；stock-profile 不保留產業欄位 | `snapshot_composition_gap`＋`semantic_gap`；需有效時間 membership 與 peer contract |
| Positioning 類別／分母／cross-check | features 把 investor_type 全部加總；分母按最近 N 筆 volume，未按日期 join | `semantic_gap`；獨立 cross-check source 仍 unknown |
| Quant 日期對齊 | beta 將兩條 series 尾端按筆數 zip，沒有交易日期 join | `semantic_gap`；價格窗口以交易日期驗證 |
| Event severity | normalizer 只讀 upstream severity；features 無 taxonomy；有事件但 severity=null 時 baseline score 可為 100 | `semantic_gap`；需 versioned deterministic taxonomy，不補零 |
| 財報 PIT | MOPS adapter 明確 `publication_time_authoritative=False`；availability 為 Janus fetched time | `provenance_time_gap`；可證明首次接收，但不能證明歷史官方發布時間 |
| 特殊會計欄位 | 官方最新 2327 回應亦有空欄 | `unknown`；空欄不是 applicability 證據，不能自動標 not_applicable |

本表未代替完整 machine-readable Gap Matrix，不構成 S0 acceptance。

## 官方 bounded source 查核

2026-10-02 唯讀取得 [TWSE OpenAPI schema](https://openapi.twse.com.tw/v1/swagger.json)，`t187ap05_L`、`t187ap06_L_ci`、`t187ap07_L_ci` 均未宣告歷史 query parameters。實際 2327 回應：損益／資產負債為 2026 Q2、出表日期 1151002；月營收為 11508、出表日期 1150917。這些回應未寫入 Core，也不能倒填到 2026-10-01 pinned snapshot。

[官方財務比較平台說明](https://mopsfin.twse.com.tw/terms) 提供自 IFRS 起的歷史財報及指標口徑，顯示歷史資訊並非完全不存在；但不能把網站存在當成穩定、已核准的 ingestion API。需另核對取得路徑、publication／revision evidence、授權與頻率。

FinMind 現行 fallback 僅 `TaiwanStockFinancialStatements`、window 400 日、publication 非權威；舊全市場 acceptance 明確記錄無合規 market-batch endpoint。不得把它當成已供應 12 季／12 月／三表的歷史解法。

## 可重跑 dev 檢查

[`ops/data-supplement-s0-probe.py`](../ops/data-supplement-s0-probe.py) 使用正式 catalog／pinned snapshot，檢查 input 四 symbols 的 raw／qualified periods、metrics、日期與 provenance 欄位；驗證 input／manifest hashes，不呼叫模型、不寫 publication。

2026-10-02 dev Job execution `janus-intelligence-mart-t9zd5` Completed=True、succeededCount=1、exit(0)。結果見 `ops/data-supplement-s0-runtime.json`；provider_calls=0、publication_writes=0。四個 targets 原始財報都有 2025Q1～2026Q2，但 qualified period 都只有 2026Q2；2327 有 628 筆因 missing_availability_time 被排除。OHLCV qualified rows 分別為 16／21／17／21。部分 machine-readable matrix 見 `ops/data-supplement-s0-gap-matrix.json`，尚非完整 S0 acceptance。

## FinMind 試連與 Stop-and-Discuss

使用者明確要求試連 TWSE／FinMind。2327、2023-07-01～2026-10-01 的四次無 Token API request 均 status=200：損益 194 rows、資產負債 1178 rows、現金流 298 rows，各涵蓋 12 季；月營收 39 rows。Summary 見 `ops/data-supplement-source-probe.json`。此四次匿名 probe 未安裝 SDK、讀取 credentials、付費呼叫或寫入 Core；後續 token 查核另記於下文。

三類財報回應沒有 publication／availability 欄位；[FinMind 官方說明](https://finmind.github.io/tutor/TaiwanMarket/Fundamental/) 亦指出月營收 create_time 是入庫時間，並非公司官方公告時間。不能把 fiscal date 或今天 fetched time 倒填成歷史發布時間。歷史數值窗口已找到，但 PIT-qualified 窗口尚未成立。

原 Stop-and-Discuss 的精確缺口為歷史財報 publication／revision evidence。使用者已明確採用保留 PIT requirement、bounded 官方 MOPS 申報／更正查核與 FinMind 數值勾稽方案，授權私人內部用途、免費來源；未核准付費來源、validator 放寬或 requirement 降級。目前接續 S0 investigation，不代表缺口已解決或 S1／S2 已完成。

FinMind [資料授權說明](https://finmind.github.io/Disclaimer/) 未授予原始資料對外再散布／鏡像權利；本次只做 bounded private/internal probe，正式接線仍須保存 dataset-level attribution／用途／retention admission。

使用者要求尋找既有 token 後，已在 `janus-runtime-bundle` 找到非空 `finmind_api_token`。僅輸出 secret／field name 與 has_value=true；未輸出或寫入 token。現行 `first_batch.dataset_adapters` 的 FinMind HTTP request 尚未讀取此欄位或加 Authorization header；前述四次成功試連都是匿名請求。Token 存在不等於方案額度／付費資格已確認，也不會補出回應原本沒有的權威發布時間。

驗證：input／manifest hash assertions 與 dev 正式 snapshot 讀路徑成功；2327 21 筆 OHLCV／28 筆 qualified financials 的 artifact asserts 通過；Python compile 與 git diff --check 通過。完整 S0、全 active targets、修復／CI／部署／live post-fix acceptance 均未完成。

## MOPS 官方申報與更正證據

- 官方索引：`https://doc.twse.com.tw/server-java/t57sb01?step=1&colorchg=1&co_id={symbol}&year={ROC_year}&mtype=A`。四個 pinned targets 的 2023Q3～2026Q2 均取得 12 筆中文合併財報上傳日期時間，共 48 筆；另保留 2023Q1/Q2 作期初查核。來源年度 HTML hash／filename／時間見 `ops/data-supplement-filing-probe.json`。
- 2327 2026Q2 官方上傳時間 `2026-08-14T15:04:28+08:00`。取得官方 PDF，SHA-256 `cf0bc1a51edb3fc3fc0160310c7c903b36e3766ce80fb3eaa8d949bc0c4d9561`；損益表當季 Revenue 44,456,327 仟元、Net Income 9,456,351 仟元、EPS 4.59 與 FinMind 數字一致。半年累計 EPS 8.48 減 Q1 3.90 是 4.58，不能取代明列的單季 4.59；面額變更亦需保存原始／重編 EPS 口徑。
- 更正彙總：官方選單 `/mops/web/t56sb31_q1`，action `ajax_t56sb31_q1`；先經 `/mops/api/redirectToOld` POST `{apiName, parameters}`，再讀官方回傳的 `mopsov.twse.com.tw` URL。參數包含 TYPEK、民國 year、兩位 season、step=1、firstin=1、off=1、encodeURIComponent=1、isQuery=Y。
- 完成上市市場 12 季查核：每季中文合併財報更正 27～93 筆，四個 pinned targets 未見匹配更正。這只代表此查詢範圍未見紀錄，不證明所有原始數值版本已還原；見 `ops/data-supplement-correction-probe.json`。
- 實際欄位：公司代號、公司名稱、公告日期、資料說明、更(補)正內容、詳細資料；公告日期僅日精度。1605 2026Q2 detail 顯示四大報表「無」、財報附註關係人交易更正；不能把每筆更正當作 EPS 或三表 canonical 數字改版。SKEY／RID 是官方定位參數，不能猜成版本號。
- 新增 stdlib parser `financial_publication.py`，驗證 headers、查詢期別、公司與 filename／detail identity。錯誤頁／缺日期／錯公司 fail closed；保留 `numeric_revision_verified=False`。此模組尚未接入正式 ingestion，未回填 Core。

## 使用者提供的批次首次申報路徑查核

官方選單可找到免公司代號的「會計師查核(核閱)報告」`/mops/web/t163sb14`，其 action `ajax_t163sb14`。實測上市 114Q2 回應 299,458 字元，欄位為公司代號、公司簡稱、簽證會計師事務所名稱、簽證會計師、簽證會計師、**核閱或查核日期**、核閱或查核報告類型。沒有公告日期、申報時間或上傳日期，不能拿核閱日期當 Version 1 publication。

`ajax_t163sb01` 不帶公司代號的測試回覆「請輸入公司代號」。使用者提供的 TWSE URL 仍只有網域、沒有 reportDate 路徑；裸網域本機 DNS 查詢失敗，改測官方 `https://www.twse.com.tw?year=114&season=2&response=json` 得 HTTP 200 HTML 首頁，JSON parse 失敗。尚未驗證到該 reportDate API，不推論它不存在，也不猜測 API 路徑或寫入 source registry。

已找到的官方索引路徑可繼續做四個 targets 的數值／版本勾稽，不依賴未驗證的全市場時間表。首次申報時間＋更正日期不足以單獨重建歷次數值，更正後值必須另綁文件／hash／口徑；保留歷次版本，不能覆蓋掉舊值。日期精度不冒充秒精度；PIT 不等於已解決生存者偏差。

新增 parser 的兩個 targeted tests 通過；真實 16 份年度索引與 12 份季度更正 HTML 均解析成功。未完成：全 active targets inventory、12 季數值版本勾稽、完整 source admission、正式 adapter／Core 接線、修復後 replay／CI／dev deployment／live acceptance。

補充重測：使用者新增 `queryName=co_id` 後，再經官方 redirect 測 `ajax_t163sb01`，HTTP 200、2,505 字元，仍為「請輸入公司代號」，沒有公告日期／表頭；官方 `t163sb01.js` 定義 companyId input，未含彙總報表 label。結果見 `ops/data-supplement-announcement-probe.json`。不將這個回應當全市場首次申報時間表。

## 全 active targets 與跨產業品質查核

唯讀 GCP execution `janus-intelligence-mart-8v2vh` Completed=True、succeededCount=1、exit(0)。透過正式去識別化 target projection，確認 pinned as-of 的 active symbols 為 `2327`、`2330`、`5876`；與四個 baseline 聯集為五檔。`ops/data-supplement-s0-runtime.json` 保存 qualified features／dataset counts／rejection reasons；`ops/data-supplement-gap-matrix.py` 重建 95 列五角色需求與 45 列 dataset time semantics，仍屬 S0 partial，不能把每列已分類當作已修復。

跨產業 probe 擴為 11 檔：1102 亞泥、1301 台塑、2002 中鋼、2327 國巨、2330 台積電、2412 中華電、2801 彰銀、2851 中再保、2882 國泰金、4958 臻鼎-KY、5876 上海商銀。官方名稱／產業碼與四個 FinMind datasets 的 response hash／結構檢查見 `ops/data-supplement-source-quality.json`。三表均取得 12 季、月營收均 39 筆；2026Q2 的 224 個可比較金額項目與官方 Q1/Q2 公告一致。所得單季損益金額以累計差額比對，資產負債以期末 snapshot 比對，均檢查公司／期別／報表範圍與仟元→元；EPS 不使用累計相減。

四個金融類樣本（2801／2851／2882／5876）的 FinMind 最新損益資料缺 EPS，不是官方沒有值。2801、2851、2882 的官方 PDF 2026Q2 單季 EPS 分別為 0.51、5.61、2.80；文件 hash／頁碼／口徑保存在 source-quality evidence。2851 使用個別財報，不能與合併 scope 混用。1102 是亞泥；4958 是電子零組件的臻鼎-KY，不是網通。

## 官方 inline XBRL 歷史三表／EPS

從官方財務報告公告回傳的 `mopsov.twse.com.tw/server-java/t164sb01` 連結，以 CO_ID、SYEAR、SSEASON、REPORT_ID=C 取得五檔 2023Q3～2026Q2 的 60 份財報。4958/2023Q4 一次 HTTP error 後有限重試成功。查核腳本與 evidence 為 `ops/data-supplement-xbrl-probe.py`／`.json`，未寫入 Core、未呼叫模型。頁面混有 Big5／UTF-8；保存原始 bytes 與 SHA-256，以可還原的 byte mapping 解析 ASCII XBRL identifiers／numeric facts，沒有用 replacement characters 猜測數字或解讀中文 prose。

Parser 檢查 primary report 的 CompanyID／Year／Quarter／ReportCategory、context entity、起迄日、dimensions、unit／scale／sign、conflicting facts。分開保存當季、累計與 snapshot；generic footnote Amount1／Amount2 不當作 statement metric。2327 的 2026Q2 EPS 為單季 4.59／累計 8.48；2023Q3 單季 11.60；5876 的 2026Q2 為單季 1.04／累計 2.08。Q4 只有年度 EPS 的情況保留年度口徑，不推算單季 EPS。

歷史有限 metric 比對共 469 項，其中 445 一致、24 不一致，涉及 2327 資產負債、4958 現金流、5876 EPS／資產負債／現金流。最新季度的一致性不能推論歷史數值一致。差異仍需以官方 PDF／原始或重編版本辨識；原始數值版次與上傳時間尚未完成 binding，因此 `numeric_revision_verified=False`，不把索引時間自動填成這些 XBRL 數值的首次 publication。

月營收仍有獨立 PIT 問題：官方 `t05st10_ifrs` 已驗證可查歷史數值，但 2327/11508 JSON 沒有正式申報時間；FinMind `date` 為月份記錄，`create_time` 是入庫日期，不能冒充公告時間。官方法定申報期限也不能當作每家公司實際發布時間。

## 使用者追加營運順序

2026-10-02 使用者先接受月營收缺官方歷史申報時間「有資料就用」，再明確放寬整體驗收為「有資料優先」。已同步 WBS／TODO／storage contract：已核對數值可供目前研究，缺歷史時間／原始版次或完整 feature 明示限制，不再單獨阻擋交付；取得前的歷史 PIT 回測仍不得使用未知版本。資料接線及 live 驗收尚未完成。

歷史差異另以三份官方 PDF 查核：2327/2023Q4 資產負債、5876/2023Q3 EPS 與營業現金流、5876/2025Q1 資產負債，所查項目均與 XBRL 相同，與 FinMind 不同。PDF hash／頁碼見 `ops/data-supplement-xbrl-probe.json` 的 `official_pdf_crosscheck`；未查的其他項目不推論已通過。財報取值優先採官方 XBRL／PDF，FinMind 作勾稽或明示 fallback。

順序固定為補資料及驗收 → 每日增量收集 → 獨立週六品質檢查。每日是檢查是否有新期別／新交易日、缺期、失敗或更正；沒有新資料就跳過，不每日重抓全部歷史。週六結果只顯示於 Admin UI，先不建立 Codex automation／通知或 Email。排程、UI、完整操作文件尚未接線／部署，不能當作既有功能。

## 資料優先接線 checkpoint

`normalise_xbrl_financials` 將 60 份已驗 hash 的官方財報正規化為 642 筆研究候選值：資產負債 240、損益 342、現金流 60；五檔各 12 季。此受控 mapping 只接已辨識的 IFRS concepts，沒有將所有 footnote facts 當成報表欄位；缺欄位保持缺值。年度／累計 EPS 不假造單季值，`published_at` 保留 null。快取原始檔本次驗證時已持有，候選使用 `validated_archive_receipt`，不宣稱已知道原始首次抓取時間或歷史首次發布時間。

Core 新增獨立 `version_at`，允許未知 `published_at`，保留 receipt availability 與來源／口徑。相同值重用、同版次衝突拒絕、新版次追加；舊表採 additive schema，不改寫舊快照。DuckDB natural-key／hash 的時區正規化一併修復，避免 UTC 與台北時間代表同一 instant 時被判成不同 key。

51 個 targeted tests 通過（Core／DuckDB／parser／gap matrix／既有 adapters／Mart pipeline），包括 UTC↔台北 key、未知發布時間、新值追加、舊 schema 與舊 snapshot 保留。真實 642 筆候選另在本機 Iceberg 寫入並讀回，重跑 reused=642、snapshot 不變；這是 local real-data check，**不是 GCP dev live acceptance**。新資料尚未寫入正式 dev Core，尚未 commit／部署；完整 source adapter／Mart consumer、每日與週六批次／UI 仍待完成。
