# 系統建置與驗收補強

更新：2026-10-15；狀態：文件規劃已納入，實作／部署／驗收未因此完成。
本文件補強既有 [持股優先](holdings-first.md)、[全市場](full-market-batch-policy.md)、[五角色](specialist-engines.md) 與 [四頁UI](../ui/visual-first-four-pages.md)；不另建工作佇列，執行只看 [TODO D01～D08](../todo.md)。

## 1. 需求與架構決策

**ACCEPTABLE WITH GUARDRAILS。**先讓持股、研究資料與驗收可相信，再增加分析能力。主要問題是文件漂移與剩餘整合證據，不是缺更多模型／服務。當前用途為投資研究及人工記帳；不新增自動下單、通用聊天或另一個排程總控。

| 維度 | A：既有系統漸進補強（採用） | B：抽出獨立分析／讀模型服務 |
|---|---|---|
| 價值 | 直接補齊持股、UI、研究驗收 | 可獨立擴展分析與讀負載 |
| 架構／速度 | PostgreSQL serving、Iceberg canonical、有界Jobs；現有路徑修正較快 | 新服務契約、部署及資料同步，交付較慢 |
| Cloud Run／DB／網路 | 查詢有界、先量測、沿既有連線與資源上限 | 新連線池／流量／故障邊界需重估 |
| 成本／維運／安全 | 無新增資源；用量仍依既有授權 | 增加服務、IAM、觀測與潛在付費面 |
| 失敗隔離／回復 | 區塊partial、既有lease／版本rollback | 服務隔離較強，但跨服務回復更複雜 |
| 複雜度／維護 | 小範圍契約與回歸 | 長期更多同步與版本責任 |

優先A。只有量測證明現有邊界無法達SLO且有成本／安全授權，才重評B；不為文件整齊重構runtime。

## 2. 四頁與持股操作（D01～D03）

| 場景 | 顯示／操作契約 | 驗收 |
|---|---|---|
| 今日 | 一個主訊息，個人可信異動→市場／TAIEX fallback；缺研究不占空卡 | 已有行情可見，不等LLM／深度圖 |
| 關注 | 可按名稱、當日變動、資料狀態檢視；數值缺失固定置後並保留項目，非模型推薦排序 | 同一資料日期／排序穩定；過期值不冒充今日；排序改動納D03 |
| 持股 | 累計未實現／報酬一列；當日每股變化另一列；資料狀態有文字 | 日變化不叫交易實賺；部分缺價不抹掉已知股數成本 |
| 個股 | 短價量＋通用圖表先於研究；主圖按需讀取 | 同期間、同單位、缺口斷線；一點資料不畫趨勢 |
| 試算→保存 | 顯示預估淨收付、剩餘股數／成本、賣出預估已實現；送出重驗版本 | 試算唯讀；未知保存先查結果，用同冪等key，不誤報失敗後重複入帳 |
| 刷新 | 「更新股價」與「重新計算損益」分名，成功後顯示資料日期或進度 | 前景60秒revalidate、背景停止、手動節流；不能讓spinner蓋整頁 |
| 歷史報表 | 市值、損益、現金流分名；同checkpoint，缺價顯示受影響範圍 | 無完整cash ledger不稱總資產；出入金不當投資報酬 |

新增「情境影響」限唯讀、沿既有backend試算：若未來要呈現交易後持股權重或現金餘額，先證實完整估值／cash來源；缺任一分母則不算。這屬後續構想，未列本輪D01必過條件，不自動建立下單或風控建議。

可及性採既有44×44 CSS px主要觸控目標；不是把WCAG AA最低24px誤寫成44px。圖表提供文字／表格等價資料、鍵盤焦點、放大文字不截斷，漲跌用正負號及文字輔助。user-app的損益負值用減號，不以會計括號混淆。

## 3. 資料與API界面（D01～D04）

沿既有schema，不因本文件一次加入所有新欄位。每個需補強的response先核對現有欄位或等價資訊；缺失才版本化擴充：資料日期／來源／狀態、owner上下文、ledger或publication checkpoint、coverage及安全錯誤原因。時間顯示Asia/Taipei，存儲依既有UTC契約；received_at不替代quote_at／available_at。

首屏依 PostgreSQL bounded read；圖表按symbol／日期範圍／row cap有界。cache identity至少區分scope、資料版本與必要查詢參數，私人cache隔離owner並在登出清除；舊回應不得覆蓋新owner／ledger。未知終態先查request，不盲retry；同owner序列化與跨owner隔離保留。

交易費稅與券商資料依既有規則，不從外國UI參考推導台股稅制；不新增付費行情、隱性來源fallback。總控接續Core-ready／dirty queue／snapshot，沒有需求不分鐘掃全市場。

## 4. 五角色品質及模型選用（D07）

五個角色不是五個必須勝出的ML模型。每個角色獨立列資料可用、方法有效、部署及產品publication四種狀態；baseline可用不代表challenger有效。

| 角色 | 維持基準／挑戰者 | 主要驗收與不採用條件 |
|---|---|---|
| Fundamental | 財務規則；LightGBM challenger | 期別／單位／EPS及成長品質、60/120日候選期限；財報修正與時間假設揭露，無足夠成熟樣本不聲稱優勢 |
| Valuation | 同產業相對估值；LightGBM／CatBoost | 虧損PE、缺值與極值；同期間baseline、train/OOS差距及成本後結果；缺DCF輸入則unavailable |
| Quant | 零訊號／簡單動能／Linear；樹模型／Qlib challenger | 同日橫斷面Rank IC、分期穩定、換手／成本後spread與回撤；歷史membership不完整需揭露 |
| Risk | CVaR／beta／drawdown；Markov challenger | 尾端覆蓋、狀態切換、分高低波動環境與月度log score；15/23月勝出不等於顯著 |
| Event | 官方parser／rules；本機classifier | training-use、真實reviewer、event/revision去重，時間／事件群組隔離；macro-F1、各類precision/recall、校準；分類機率非上漲機率 |

研究先凍結manifest：任務／投資期限、當日歷史母體、來源與available-at、feature/label版本、train/validation/test日期、主要baseline／指標、成本情境、promotion條件。最後test不參與挑參；若反覆使用便改標validation並保留新的未觸碰時段。試驗次數與失敗也保存，禁止只報最佳模型。

時間切分以**交易日期群組**而非逐股票列分割；所有同日股票在同fold。label end／available-at跨越邊界的樣本purge，gap按最大標籤期限／發布延遲決定，不任意固定天數。缺值填補、標準化、特徵選擇只fit train；scikit-learn TimeSeriesSplit本身不處理股票panel分組、財報修正或事件重疊，不能直接當完整防洩漏證明。

成本情境需預先定義手續費／稅／滑價／換手及不可成交限制；日頻訊號不能假定當日收盤已知後仍成交於同一收盤。報告按月份／市場／產業／流動性分組、有效樣本及不確定性；相關樣本採時間區塊評估，不把每日股票數當獨立樣本數。數值門檻在研究開始前版本化，不在此臆造保證獲利門檻。

`strict_pit=false`財報研究維持既有使用者核准：可以比較，但不可改稱嚴格PIT回測；單獨揭露修正／估計時間占比與敏感性。舊B9診斷的保守blocker須映射到對應用途，不能刪guard來取得PASS，也不能反過來封鎖已核准研究。升級需獨立evidence、artifact hash／模型版本、publication及rollback；不自動promotion。

## 5. CEO及研究到產品的邊界（D08）

重用已存在OmniGatewayGeminiProvider；技術P0-V與正式Owner報告分開。只有有效角色／validated Fact Pack就緒才整合報告；資料衝突、情境、失效條件、來源與unknowns都可追溯，LLM不發明數字或決定publication。研究／報告不等於個人買賣指令；使用者目標價與模型估值分名。分析由手動request啟動，specialist變更只更新stale／material delta。

## 6. FinOps與完整性（D06）

壓縮會重寫檔案，舊snapshot保留時object數可能上升；compact PASS不等於storage或I/O下降。snapshot expiry、orphan removal、manifest retirement各驗其保護集。研究／模型／publication／private引用未完整讀回時fail closed；不可僅按檔齡整桶刪除。orphan保留窗需超過可能進行中的寫入時間，沿目前核准7日及generation fence，不直接採外部工具預設值。

I/O比較固定資料量、股票數、冷暖比例、窗口與request種類，分開ReadObject／GetObjectMetadata及bytes，記錄一次性maintenance。先找重複metadata load／manifest掃描／逐檔HEAD／小批commit的實際呼叫證據，再以共用reader、exact-snapshot reuse、批次讀及合併寫入最小修正；禁止未量測就承諾百分比。

## 7. 實作交接與風險

| 工作 | 已確認入口 | 驗證與恢復 |
|---|---|---|
| 交易／持股 | `services/api/app.py`、`repository.py`、`trade_calculation.py`、`trade_fees.py`、`private_recalc_queue.py` | 版本／冪等／隔離與live checkpoint；append-only更正，不回寫假交易 |
| 四頁 | `apps/user_app/lib/final_ledger.dart`、`final_watchlist.dart`、`final_stock_detail.dart`、`final_today_v2.dart` | targeted／golden、真實auth截圖、P95；沿既有Preview回復 |
| 快照／全市場 | `jobs/ingestion-core/ingestion_core/__main__.py`、`full_market.py`、`batch_controller.py` | 真實caller／freshness／coverage及無重複派送 |
| 研究 | `jobs/intelligence-mart/intelligence_mart/evaluation.py`、`quant_pit.py`、`event_labeling.py`；`scripts/gcp/b9-specialist-oos-quality.py` | 固定版本、同fold baseline、OOS與artifact readback；失敗維持baseline |
| 維護 | `jobs/ingestion-core/ingestion_core/retention.py`、`tests/test_iceberg_compaction.py` | dry-run→引用fence→bounded apply→readback；不可復原資料不刪 |

以上相對入口以repo根為準，同一列省略重複目錄。實際開始前重讀main。主要風險是錯版本發布、混合時點估值、資料洩漏與引用誤刪；每項由版本／checkpoint／時間切分／fence控制。新費用／IAM／不可逆刪除仍走PROJECT_RULES，不增人工OAuth例行gate。

## 8. 外部依據（2026-10-15查閱）

- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/)及[Target Size Minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum)：可及性參考，Janus保留自身較大的主要觸控目標。
- [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)：時間順序及gap的工具語意；panel日期分組及金融purge是本案追加設計。
- [Apache Iceberg Maintenance](https://iceberg.apache.org/docs/latest/maintenance/)：區分snapshot到期、孤兒檔與小檔重寫；不直接複製Spark命令到PyIceberg runtime。

外部方法是設計依據，不是本專案實作／runtime證據；不引入新依賴或付費服務。
