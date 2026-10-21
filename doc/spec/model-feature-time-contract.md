# D07｜X/Y 因子、清洗整合與滾動時間契約
更新：2026-10-21。設計契約，非已部署 pipeline。角色/模型表見 [五分析師](specialist-engines.md)，採集見 [Colab/Drive](research-collection-gas-drive-colab.md)。

## 1. 三個不同的窗口
- **特徵回看窗口 L**：今天推論所需歷史，例如20/60/120交易日，不是模型只學一個月。
- **訓練窗口 W**：多檔股票多個歷史時點的X與已成熟Y；初始研究以已收兩年左右資料盤點為起點，不保證兩年就有足夠跨景氣/季報樣本。
- **預測期間 H**：模型要預測的未來5/20交易日；推論當下沒有Y。Y成熟後才能評分及加入下輪訓練。
- 日常推論使用固定已發布模型＋新X；不每日fit。建議每月人工評估Quant/Risk是否重訓、Fundamental/Valuation隨新月/季資料評估、Event隨新增合格標註評估；都不是新建自動重訓排程。

## 2. 每天怎麼移動
以 T 為最近已完成、資料可用的交易日，τ為執行截止時間。日價量X_L(T)取交易日序列 [T-L+1,T]；L日報酬需L+1個價格。
| 執行 | 價量截止 | 20交易日特徵 |
|---|---|---|
| 10/1盤前 | 若9/30為最近完整交易日，T=9/30 | 截至9/30最近20交易日；起日由交易日曆算 |
| 10/2盤前 | 若10/1有交易且EOD已到位，T=10/1 | 移除最早一日、加入10/1 |
| 週末/休市後，尚無新EOD | T不變 | 窗口不動；只更新已新公布的事件/低頻資料 |
這些日期是條件示例，不宣稱2026特定日期必為交易日。
若明訂「最近30個曆日，不含執行日」，10/1為9/1–9/30，10/2為9/2–10/1；使用者舉9/2–9/30是29個曆日。交易模型預設20交易日約一個月，不用固定月初或每天日曆加一取代交易日曆。
盤後T當日完整EOD可用才納入；早到/晚到財報依τ單獨判定。盤前/盤後可共用相同T但不同τ，故事件資訊可能不同。
停牌/漏資料不是休市。以市場交易日網格檢查，缺一日不把20筆跨很久的觀測冒稱20交易日；停牌不造零報酬，另記missing/stale或停用相依模型。

## 3. 原始資料到X的最小流程
| 層 | 工作 | 必要輸出/檢查 |
|---|---|---|
| 原始取得 | 沿既有正式Core增量；研究Colab按月檔讀取 | source/授權、raw hash、fetched_at、symbol/market、資料期、原始版次 |
| 清洗 | 民國/西元、時區、代號、逗號、單位與空值；去重/修訂；OHLC一致性、量不可負 | close>0；合法0與null分離；股/張/TWD/千元固定；保留拒絕原因 |
| 時點整合 | 交易日曆、當時普通股母體/產業/benchmark、公司行動、財報公告版次 | effective_at/published_at/first_observed_at/available_at/valid_from/version；join不得看未來 |
| 因子計算 | 同股票滾動、同日期橫斷面、財務月季計算 | feature_version、L、min_points、單位/口徑、實際起訖、缺值/資料年齡 |
| X panel | 股票×cutoff/T一列供日頻角色；月/季/事件角色保留原生顆粒度 | ordered feature schema、input_hash、來源refs、training/serving parity |
| Y label | 未來資料成熟後獨立計算 | horizon、target、label_start/end、mature_at、可交易性/公司行動狀態 |
| 模型/解讀 | 固定model+preprocessor推論→版本化規則解讀 | 預測及證據、適用時段、限制、前次結果比較；API只讀 |
以上為共享程式/契約，先沿既有Mart/Colab建立，不新增獨立Feature Store服務或倉儲。

## 4. 資料集、原生欄位與衍生X
| 資料集/頻率 | 原生欄位 | 主要衍生X | 最低讀取需求/更新 |
|---|---|---|---|
| OHLCV/日 | open/high/low/close、volume_shares、turnover_twd、trade_date | ret5/20/60/120、MA距離、vol20/60、drawdown、ATR14、量比、流動性 | 120日報酬至少121價；20日量比以前20日為分母需21量；vol60需61價；有新EOD更新 |
| benchmark/日 | 市場指數close、market、date | 同窗超額/相對強度、beta、regime背景 | 同日期對齊，TWSE/TPEx benchmark明確；缺市場指數不以0補 |
| 公司行動/事件 | 分割/減資/除權息、比例/現金、effective/published time | 可比價、跳空辨識、調整狀態 | 訓練/推論同一adjustment_basis；未核對事件跨窗不產假動能 |
| 法人/日 | 各角色buy/sell/net shares | 5/20日累積淨買賣、淨買超/成交量 | 同單位，拆分自營商子項避免重算；缺日不當0 |
| 月營收/月 | fiscal_month、revenue、published/observed、revision | YoY、三月合計YoY、成長加速度 | 當月同比13月；三月同比15月；公告後才變更 |
| 財報/季 | 單季EPS/淨利、收入/毛利/營益、equity/debt/CFO、scope/share basis | EPS差額、margin/ROE/負債比/CFO品質 | 同口徑可比；不把累季當單季；比率分母合法；公布後更新 |
| 估值/日 | PE/PB/yield、可比EPS/BVPS、產業 | 自身有效窗口分位、同業差距、估值情境 | 兩年約504交易日僅目標，需足量歷史；不足標實際期間，不阻擋現值 |
| 公告/事件 | event_id/text/type/published/observed/effective/revision | 類別、距已確認事件日、近期事件數/修訂 | 去重；事件日期未知不猜；文字權利另核 |
| universe/有效期間 | market/security_type/list/delist dates、industry/membership | 合格母體/產業cohort、缺值旗標 | 歷史下市股保留，現行名冊只能PROBE |
「缺值旗標」不是把未知補成事實。若模型允許imputation，統計量只在training fold fit，保留missing indicator；必要欄位缺失則停該角色。異常值不直接刪掉真暴跌，先查公司行動/單位/來源。

## 5. 公式與label定義
令 P^a 為已驗證同一調整基準的價格、r_t=ln(P^a_t/P^a_{t-1})；指數B採明示相容基準，價格報酬與總報酬不能混用。
- ret_L=P^a_T/P^a_{T-L}-1；rs_L=ret_L-(B_T/B_{T-L}-1)。
- ma_distance20=P^a_T/mean(P^a_[T-19:T])-1。
- volume_ratio20=V_T/mean(V_[T-20:T-1])；分母0→null。
- vol20=sqrt(252×mean(r_[T-19:T]^2))，沿現有Risk試點RMS定義；drawdown60=P_T/max(P_[T-59:T])-1。
- revenue_yoy=R_m/R_(m-12)-1；revenue_3m_yoy=sum(R_[m-2:m])/sum(R_[m-14:m-12])-1。非正分母或不可比→null/差額說明。
- Quant研究Y_return,H=P^a_(T+H)/P^a_T-1；Y_excess,H=Y_return,H-(B_(T+H)/B_T-1)；Y_up=1[Y_return,H>0]、Y_outperform=1[Y_excess,H>0]，分別H=5/20。交易成本不混入這兩個名稱，另報成本後效用。
- **可交易回測另算**：截至T收盤才生成的訊號不能以同一T收盤成交；預設下一可交易日開盤進、H日持有後約定收盤出，明列進出索引、費稅/滑價/漲跌停/停牌/開盤缺價；沒法成交就按規則跳過/延期並報涵蓋，不能拿close-to-close當實績。
- Risk Y_RV20=sqrt(252/20×sum(r_(T+1:T+20)^2))；現有實作的label_matures_on=T+20有效交易日。實際known時間還需等最後來源到位。
- Risk擴充 Y_MDD20 = max（1−P^a_(T+j)/P^a_(T+i)，其中0≤i<j≤20）；這是窗口內peak-to-trough，與min(P/P_T-1)的入場後最差損失不同。分位模型Y是Y_return,20，不從波動直接杜撰機率區間。
- Fundamental在已公布m期資訊時預測m+1營收YoY；可比EPS次目標為下一季EPS或EPS差額。label須待真正公布並註明使用首次版或事後修訂版；兩種不混為同一評估。
- Valuation Y為當時合格同業log(PE)/log(PB)，不含非正倍數；此為相對定價估計，未來60/120日超額報酬僅成熟後評估效用，資料不足不訓練長期模型。
- Event Y為人審語意類別/重要性。若獨立評估市場反應，以公告實際可得後第一可交易時點對齊，避免盤後公告配上公告前報酬。

## 6. as-of join 與防止未來資料
- τ前已可取得的最新合法版本才可進X。只有財報期末日而沒有可證明公開時間，不能假設當天市場已知。
- 每日沿用最近已公布季報屬狀態延續，不是每一天一個獨立季報訓練樣本；附age_days。禁止從未來公告向過去backfill。
- 今日下載的歷史檔 fetched_at 是今日，不冒充歷史published_at；有可驗證歷史首次版可用原published時間，否則保留non-strict研究，不能通過嚴格promotion。
- 修訂保留版本：實際曾產生的歷史預測與input_hash不變；新版本只影響新cutoff或另標restated研究。
- 公司行動調整版本固定；不能把事後已知行動/最新產業與存活名冊無聲灌回所有歷史日期。
- 暫不設定全模型共通「所有資料必須齊兩年」門檻；每個feature有自己window/min_points，每個role有自己必要欄位。

## 7. 資料保存、增量與訓練/推論一致
研究Drive月檔是保存分區，不是模型窗口。一次跨月讀取所需最長L＋warmup；滾動後每日只追加新日期與有修訂的period，不每天重抓整月/整市場歷史。
現有Colab只封存閉合月，當月即時推論仍走正式Core→Mart；不把當月研究採集尚未支援當成正式每天推論阻擋。
若用120日X，每日維持至少121有效價格；若同時估兩年分位需另讀約兩年歷史，不能只下載近一月卻宣稱算60/120日指標。
共用versioned feature builder/contract：研究與正式來源可不同，但欄位/單位/調整/available-at/缺值/排序/分母完全對齊；同輸入sample應得同X。差異須修正或停該模型，不偷偷換公式。
保留模型使用的月檔版次、特徵/標籤與cohort manifest/hash足以重現OOS；不依賴已清掉的Core舊snapshot，也不恢復舊BQ export必經路線。

## 8. 訓練窗口與OOS切分
初始建議：取得約24月資料後，可用前12月作首輪train、後3月validation，往前滾動3月，多fold評估；最後3月作完全未調參holdout。這是規劃示例，必須扣掉最長warmup與未成熟label，不保證剩下足量樣本。
- 以「唯一交易日期」切train/validation/test，同日所有股票同一fold；逐股票隨機切列或把同日股票分散到不同fold均不可。
- 每fold只用mature_at≤train_cutoff的Y；清除label interval與下一fold重疊的train列。20日Y需依實際交易日/成熟時點purge，不以20筆股票列的gap代替。
- scaling/imputation/winsorization/feature selection/超參數/校準只在相應train或validation fit；test僅一次最終評估。
- 同期跨股票及重疊H日label高度相關，報告unique dates/months/events與block uncertainty；大量股票列不等足夠時間證據。
- 日頻Quant/Risk可先研究；兩年每股僅約8季，Fundamental季模型與估值長期效用不因股票多就自動通過。必要時保留規則，不能為五模型湊齊而發布。
- 每次新訓練版本記錄實際起訖、cutoff、label maturity、母體、source/feature hash、dependency版本、seed及驗證結果。


## 9. 資料量與結果回收路由
前節24月切分是短史試點示例；成熟研究建議量按[生命週期第2節](model-lifecycle.md#2-建議資料量研究規劃目標不是保證有效或統一硬門檻)。目前README建議2025-01～2026-09僅21月，不代表已實收。日/週推論、各角色結果成熟、前瞻評估與每月重訓決策見該文件第6–10節；固定預測不可用新版回寫。

