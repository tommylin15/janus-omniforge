# Janus × OmniForge — UI Specification

版本：1.2
範圍：Flutter + Material 3 User App、獨立 Admin Web、responsive、a11y 與 FastAPI/UI data contract

## 1. UI 原則

- UI 只呈現後端／Mart 已持久化資料，不在前端重算分數或補資料。
- blocked report 不渲染；null 不顯示 0。
- 明確區分 loading、error、empty、unavailable、partial、stale、fallback、blocked。
- confidence 固定標示為「資料／分析信心度，非獲利機率」。
- 不輸出保證獲利、確定買賣指示或無依據目標價。
- 所有來源只取當前資源／當前日期自己的 provenance。
- User 與 Admin 是兩個獨立入口；User App 不出現 Admin 導覽，Admin Web 不混入小白的市場閱讀動線。
- User App 使用「結論 → 原因 → 風險 → 來源」的減法層次；首屏不顯示 K 線、密集數字表格或內部 Agent 術語。
- 個人交易筆記與公開市場分析的導覽及資料狀態分離；不顯示他人持倉、公開績效排名或下單按鈕。

## 2. 視覺系統

- User App 使用 Flutter Material 3、`ColorScheme.fromSeed`、圓角 Card、清楚字階與充足留白；不引入第三方 UI kit。
- 預設支援 light、dark 與 system theme。Admin 可繼續使用現有深色 zinc 系統，不為了視覺一致破壞密集營運表格的可讀性。
- 價格漲跌依台股慣例：上漲 red、下跌 green；健康／風險語意固定為高健康 green、警戒 amber、低健康／blocking red。顏色旁必須有文字或 icon，不只靠紅綠。
- amber：warning、partial、fallback、attention；不得表示安全。
- red：blocking、critical/high、disposition、停資停券。
- 系統字型優先，不依賴 Google Fonts。
- 一般文字 WCAG AA 4.5:1；大字 3:1；focus indicator 3:1。

設計參考只吸收可驗證的版面語彙，不複製其資料模型或功能：

- [Trace](https://github.com/trentpiercy/trace)：輕量市場探索、清楚的總覽 → 詳情層級與 theme 選擇。
- [artha](https://github.com/wahyuatmaja3/artha)：以新復古／Neo-Brutalism 的粗體重點與直接文案作少量品牌點綴；Janus 保留圓角、低噪訊與金融產品所需的可信感，不採整頁高飽和粗框。
- [Financial-Management-Dashboard-UI](https://github.com/Redvey/Financial-Management-Dashboard-UI) 與 [finance-web](https://github.com/feMoraes0/finance-web)：Flutter dashboard 的 card／grid 佈局參考；User App 只保留一個主指標與漸進揭露，不照搬桌面密集圖表。

## 3. Responsive Layout

| 裝置 | Layout | Navigation | History |
|---|---|---|---|
| Mobile | 單欄，User App 優先 | Material 3 AppBar + NavigationBar | Bottom sheet |
| iPad | 兩欄可用 | NavigationRail 或 NavigationBar | Centered dialog |
| Desktop／Web | 最寬 1200px 的有界 grid，無水平 overflow | NavigationRail／Header | Centered dialog |

- 支援 safe area、`viewport-fit=cover`、`100dvh`。
- 所有主要控制、日期、圖表 toggle、展開按鈕至少 44×44 CSS px。
- Material 3 NavigationBar 主要項目高度至少 56px。

## 4. 全域殼層

### User App shell

- Material 3 `AppBar` 只放當前頁標題、資料日期與必要操作；不放 Admin 入口。
- `NavigationBar`：今日、探索、筆記、我的。熱門話題與板塊輪動屬於「今日／探索」，不再增加一排主導覽。
- 未完成項目顯示 coming soon／disabled，不可只 `debugPrint`。safe-area bottom 不遮擋內容。

### Admin shell

- 獨立 Admin URL／host 與認證邊界，保留「資料營運中心」品牌。
- 不使用 User App 的底部導覽；依桌面營運工作流提供 tabs／tables。

### Global status

- API unavailable 顯示可理解訊息，不呈現 upstream traceback。
- 可選擇顯示最新資料日、更新時間與來源健康摘要。

## 5. User App 頁面

### 5.1 今日

首屏固定順序：

1. `MarketRegimeCard`：一句話市場狀態、資料日期與信心度。
2. `DailyBriefCard`：最多三則今日重點，並列支持因素與風險因素。
3. `SectorRotationList`：前三個升溫／降溫板塊；先用可讀排名，泡泡圖放在「看完整輪動」次頁。
4. `HotTopicList`：最多五個熱門話題，顯示來源數與不確定性，不用聲量假裝正確性。
5. `CandidateHealthList`：最多五張候選股健康卡。
6. 資料日期、partial／stale／fallback 與標準免責聲明。

首頁只讀同一 `analysis_as_of` 的 `mart_daily_brief`；任一子產品日期不同時顯示 partial，不得把不同日期的最新版拼成「今日」。

### 5.2 探索

- 搜尋股票代號、名稱、產業與題材；停用股票不出現。
- 預設顯示板塊輪動排行與候選股，不先顯示 K 線。
- 進階泡泡圖可使用 X 軸「近 5 日法人買超力道」、Y 軸「力道變化」、泡泡大小「近 20 日成交金額」，並提供文字排行／表格替代內容。
- 歷史回放最多 20 個交易日，只有在 `mart_sector_rotation_daily` 已保存各日 snapshot 後才啟用。

### 5.3 個股健康檢查

固定順序：

1. `StockHeader`
2. `StockHealthCard`
3. `AiPlainLanguageCard`
4. 三項「為什麼」與三項「要注意什麼」
5. `ChipsStatusCard`
6. `CompanyEventTimeline`
7. 可收合的 `EvidenceAndSources`
8. `ComplianceDisclaimer`

K 線、五角色明細、估值指標與完整 provenance 屬「進階資料」，預設收合且不得先於健康度與白話摘要。未知／停用股票顯示 404；已啟用但沒有 report 顯示「等待下一次批次」，不得啟動即時分析。

### 5.4 個人交易筆記

- 與市場探索分頁，進入後先顯示「目前持股」、「本年已實現損益」與「待完成筆記」三張摘要卡。
- 新增交易欄位：買進／賣出、日期、股票代號／名稱、成交股數、成交單價、手續費、證券交易稅與備註。
- 使用十進位輸入、明確單位與即時格式驗證；不得用浮點數造成金額誤差，也不得預填虛構價格。
- 歷史明細支援股票與年份篩選；修正既有交易時呈現「建立更正」而非無痕覆寫。
- 年度報表顯示已實現損益、費用、交易次數與年度比較。未實現損益必須標示估值日期與缺價狀態。
- 預設成本法為移動平均法並顯示在報表；尚未核准 FIFO 前不提供切換。
- 所有 empty／loading／error 狀態不得洩漏其他使用者是否存在資料。

### 5.5 我的

- theme 使用 light／dark／system；字體縮放跟隨系統，不自建第二套縮放引擎。
- 提供「匯出我的交易資料」與「永久刪除私人資料」。刪除使用 danger zone、再次驗證與明確影響範圍，不以單次誤觸直接執行。
- 不放方案定價、預測戰績或公開排行榜；待產品與法遵另案確認後再新增。

## 6. 元件契約

### StockHealthCard（Flutter reference）

輸入欄位固定使用 `stock_id`、`stock_name`、`mart_health_score`、`chips_status`、`ai_whitepaper_analysis` 與 `analysis_as_of`。`mart_health_score` 必須是已發布 Mart 的 1–100 整數；Widget 只映射顏色與版面，不計算分數。

```dart
import 'package:flutter/material.dart';

class StockHealthCard extends StatelessWidget {
  const StockHealthCard({
    super.key,
    required this.stockId,
    required this.stockName,
    required this.martHealthScore,
    required this.chipsStatus,
    required this.aiWhitepaperAnalysis,
    required this.analysisAsOf,
  }) : assert(martHealthScore >= 1 && martHealthScore <= 100);

  final String stockId;
  final String stockName;
  final int martHealthScore;
  final String chipsStatus;
  final String aiWhitepaperAnalysis;
  final DateTime analysisAsOf;

  Color get scoreColor => martHealthScore >= 70
      ? Colors.green
      : martHealthScore >= 40
          ? Colors.amber
          : Colors.red;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('$stockName $stockId',
                  style: Theme.of(context).textTheme.titleLarge),
              Text('資料日期 ${analysisAsOf.toLocal().toString().split(' ').first}'),
              const SizedBox(height: 20),
              Semantics(
                label: '股票健康度 $martHealthScore 分，滿分 100 分',
                excludeSemantics: true,
                child: SizedBox.square(
                  dimension: 120,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      CircularProgressIndicator(
                        value: martHealthScore / 100,
                        strokeWidth: 12,
                        strokeCap: StrokeCap.round,
                        color: scoreColor,
                        backgroundColor: scoreColor.withAlpha(38),
                      ),
                      Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text('$martHealthScore',
                              style: Theme.of(context).textTheme.displaySmall),
                          const Text('健康度'),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Align(
                alignment: Alignment.centerLeft,
                child: Chip(label: Text(chipsStatus)),
              ),
              const SizedBox(height: 12),
              Card.filled(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.psychology),
                      const SizedBox(width: 12),
                      Expanded(child: Text(aiWhitepaperAnalysis)),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      );
}
```

- 健康度不是獲利機率；卡片下方必須同時提供風險與資料日期。
- `ai_whitepaper_analysis` 是 Gemini 對合格 evidence 的白話轉譯，不得在 Widget 中補字、截斷成不同結論或注入示例內容。
- partial／stale 時保留卡片但顯示狀態 banner；blocked／insufficient_data 不顯示分數圓環。

### StockHeader

- symbol、真實 name、market。
- close、change、change percent；null 顯示資料暫缺。
- 明確顯示 `market_data.as_of` 實際交易日。
- 顯示 report `analysis_as_of`，不可暗示即時報價。

### KLineChart

- 僅放在個股「進階資料」，預設收合；不是 User App 首屏或健康判斷的主要視覺。
- D／W／M period。
- MA 5／10／20／60／120／240（依資料可用性）。
- OHLCV、必要技術指標 tooltip。
- loading、error、empty、request race protection。
- Canvas 提供同步 OHLCV table／摘要。
- tooltip 支援 hover、focus、Enter、touch、Escape，不使用 title-only。
- 手勢不得造成錯誤頁面捲動。

### MetricsGrid／SentimentBar

- 偏多、偏空、中立、資料不足四態。
- aggregate score=null 時不顯示 0、勝率或方向暗示。
- 開發期 completeness 30% gate 的 insufficient 狀態需明示。

### AggregationEvidence

- 同時顯示 bull、bear、contradictions、contributions。
- 不隱藏反向證據。
- 顯示 effective weight、quality effect、governance version。

### MarketActivityPanel

- Mobile 兩欄、desktop 四欄。
- 融資融券、借券、當沖、注意／處置。
- DB 數量以股；UI 可顯示張，tooltip 保留股數。
- healthy-empty：「目前沒有資料」。
- source unavailable：「資料暫缺」。

### AnalystCard

共通：角色、direction、nullable score、confidence、summary、missing data、evidence。

- 安全渲染 Markdown 標題、清單、粗體，不執行 HTML。
- Fundamental：規則集、營收／獲利、quality flags、正負因素。
- Valuation：PE、PB、ROE、D/E、valuation score。
- Positioning：5／20／60、crowding、smart-money divergence；crowding 不用綠色。
- Quant：relative strength、volume Z、volatility、drawdown、Beta、ATR、turnover／liquidity。
- Event Risk：risk score、governance flags、catalysts、risk events；manual review 不使用確定性樣式。

Evidence 欄位：metric、value、unit、source、provenance ID、observed／published／fetched time。

### CompanyEventTimeline

- 位於五張 AnalystCard 後、Disclaimer 前。
- 依 `published_at DESC`。
- 相同類型且語意近似只顯示最新版；有實質變更的更正公告保留。
- 收合只顯示標題與發布時間。
- 展開顯示 type、severity、effective、observed、fetched、body、source。
- critical／high red；medium amber；low zinc；unknown「待分類」。
- cursor 載入更多；附件不存在不顯示按鈕。

### ReportHistoryModal

- 最多五份，日期由新到舊。
- 從角色卡開啟時只顯示該角色在所選日期的內容。
- 日期切換同步切換 report、provenance、source references。
- legacy 欄位 null／unknown，不借用最新資料。
- Mobile bottom sheet；iPad／desktop modal。

### ReportSources

- 只使用當前 report provenance。
- 依 source name 去重；fallback 明示。
- 最多顯示三則核准新聞原文。
- 不顯示 raw object URI、query string 或不安全 URL。

### ComplianceDisclaimer

- analysis as of。
- Aggregator confidence，明示非獲利機率。
- data quality、missing data、blocking／warning。
- governance version。
- risk disclosure、來源採用範圍、標準免責聲明。

### TradingJournalForm／PnLSummary

- `TradingJournalForm` 使用 Material 3 segmented button 選擇買進／賣出，日期選擇器、股票 autocomplete 與十進位數字欄位；送出前顯示交易摘要，成功後顯示 ledger event ID。
- 賣出股數大於可用持股時由 API 拒絕，UI 保留輸入並顯示欄位級錯誤；前端預檢不能取代後端約束。
- `PnLSummary` 分開顯示已實現與未實現損益，並標示估值日期、成本法與缺價筆數；null 不顯示為 0。
- 刪除／修正需二次確認並說明會建立 reversal／replacement；成功後重新讀取已持久化 ledger／Mart，不在 Flutter 本地重算正式損益。

## 7. UI 狀態語意

| 狀態 | 使用者文案 | 視覺 |
|---|---|---|
| loading | 資料載入中 | skeleton／spinner |
| empty | 目前沒有資料 | zinc |
| unavailable | 資料來源暫時無法使用 | amber |
| partial | 部分資料可用 | amber + 缺失清單 |
| stale | 資料日期較舊 | amber + 實際日期 |
| fallback | 使用備援來源 | 低調 badge + source |
| insufficient_data | 資料完整度不足，無法評估 | zinc，不顯示方向 |
| blocked | 報告未通過發布審查 | 公開端不回傳；Admin red |
| error | 服務暫時發生問題 | 安全文案，不顯示 traceback |

## 8. Flutter／FastAPI 契約

- Flutter repository 只負責 HTTP、取消過期 request、typed decoding 與 UI 狀態；不得計算正式分數、損益或 fallback 內容。
- 200 保存 response；404 依 error code 顯示不存在或等待批次；401／403 導向登入或安全拒絕；network／5xx 顯示服務錯誤。
- 不使用 SSE，不在開啟頁面時啟動 scraper、Agent、LLM 或 Private Mart 重算。

主要 public endpoints：

- `/api/v1/public/health`
- `/api/v1/public/daily-brief?date=YYYY-MM-DD`
- `/api/v1/public/sectors/rotation?date=YYYY-MM-DD`
- `/api/v1/public/topics?date=YYYY-MM-DD`
- `/api/v1/public/candidates?date=YYYY-MM-DD`
- `/api/v1/public/stocks/{symbol}/health`
- `/api/v1/public/stocks/{symbol}/reports`
- `/api/v1/public/stocks/{symbol}/kline?period=D|W|M`
- `/api/v1/public/stocks/{symbol}/events?cursor=...`

主要 private journal endpoints：

- `GET／POST /api/v1/me/journal/trades`
- `POST /api/v1/me/journal/trades/{event_id}/corrections`
- `GET /api/v1/me/journal/positions`
- `GET /api/v1/me/journal/pnl?year=YYYY`
- `POST /api/v1/me/journal/export`
- `DELETE /api/v1/me/private-data`

Private endpoint 的使用者身分只取自驗證 token／session，不接受 request body 或 query string 指定 `user_id`。所有 mutation 具 idempotency key、optimistic version 與 audit event。

## 9. Admin UI

### 9.1 `/admin/stocks`

- 頁面品牌／標題保留「資料營運中心」；若沿用左側 Admin 導覽，右側仍一次只顯示一個功能面板。
- 使用 `tablist` 分隔「股票管理」、「股票資料狀態」、「最近執行」、「資料源健康」、「核心 50 名單」、「排程與保存設定」、「資料源設定」、「AI Prompt」、「Mart 分析」。選取狀態寫入 `?tab=`，重載與分享 URL 後可還原；未選分頁不預抓大型 details。
- Desktop 顯示水平或側邊 tabs；窄螢幕可用可捲動 tablist 或等價單選導覽，但頁面標題與目前分頁名稱必須可見。tab 支援方向鍵、Home／End、Enter／Space，並正確連結 `aria-controls`／`aria-labelledby`。

「股票管理」：

- 全部股票，不套 public enabled filter；代號／名稱搜尋、每頁 10 筆。
- 新增、編輯、enabled toggle、本頁全選與跨頁保留。
- Collection 與 Analysis 分開觸發；queued 不顯示為完成。
- 有 market／report／fundamental 關聯時禁止刪除並顯示數量。

「股票資料狀態」：

- Core 最新交易日、dataset、coverage、row count、null count／ratio、DQ、quarantine、freshness、source、snapshot ID 與 updated time 使用欄列表格，不直接輸出 JSON blob。
- 表格採類 Excel 閱讀方式：sticky header、欄位對齊、排序、篩選、分頁、欄位顯示／隱藏、橫向捲動及空值 `—`；不要求 spreadsheet 公式或任意 inline edit。
- row expand／「查看」才載入明細；巢狀 quality flags、association、quarantine reason 轉成子表或 key/value definition list。raw payload、object URI、敏感 URL 與完整 upstream error 不得提供「查看 JSON」旁路。

「最近執行」：

- 最近 50 次 persisted execution；row click／「查看」才讀結構化 details。
- execution item 以 source、dataset、target date、processed／success／failure／retry、Stage／Core commit、safe message 欄位顯示，不以 JSON 作主要內容。

「資料源健康」、「核心 50 名單」、「排程與保存設定」、「資料源設定」各自只呈現對應資料與控制，按鈕不得跨面板造成用途不明。

「AI Prompt」：

- 以角色、scope（全域／產業／個股）、scope key、revision、狀態、effective time、updated by 篩選。
- 編輯五角色的 versioned prompt template；支援 draft、diff、validation、preview resolved template、activate、retire、optimistic lock 與 audit。個股 override 優先於產業，產業優先於全域。
- 顯示本次 execution 將使用的 resolved revision ID；prompt 不得包含 secret、未核准 evidence、解除 Validator／publication policy 的指令。保存或預覽不直接啟動分析。

「Mart 分析」：

- 分成「產業分析」與「個股分析」資料表，讀取已持久化的 `mart_industry_analysis`／`mart_symbol_analysis`。
- 可依 analysis date、industry、symbol、角色、prompt revision、analysis outcome 與 publication status 篩選；明細顯示 summary、score、confidence、missing data、evidence reference、Core／Mart snapshot 與版本。
- 歷史 prompt revision 與分析 artifact 只能檢視，不可原地改寫；重新分析必須建立新的 queued execution。

### 9.2 `/admin/governance`

- Typed editing。
- Group validation。
- Diff preview。
- Immutable revision history。
- Optimistic lock。
- 顯示 approved／development-default／pending。
- Workflow 使用 immutable snapshot，不讀取未提交表單。

### 9.3 `/admin/data-sources`

- 只讀 persisted telemetry，不在 page load 呼叫上游。
- source + dataset 卡片：status、sample count、success rate、latency、last fetched、latest observation。
- 顯示 empty、schema drift、fallback、rate limit。
- 顯示安全 batch 摘要，不顯示 query、raw payload、URI、完整 error、帳號或 secret。
- 同一能力亦可嵌入「資料營運中心 → 資料源健康／資料源設定」分頁；不得因此移除資料營運中心入口。
- 候選 adapter 審查表顯示 license／terms 證據、robots／API policy、rate limit、retention／刪除／再發布、穩定性量測、欄位與內容重複度、成本、安全、reviewer、decision time、reason 與 version。
- 只有 `official`／`approved_fallback` 可啟用；`candidate`／`blocked` 的 cadence 控制 disabled 並說明缺少的審查項目。Anue 10 分鐘排程在核准前不得執行；FinData-compatible／twstock 同樣遵守此 gate。

### 9.4 `/admin/reports`

- 篩選 blocked／manual review／insufficient／publishable。
- 顯示 evidence、blocking reason、governance version。
- block／unblock／approve 需要理由、操作者與 audit trail。
- 不可直接修改原始 evidence 或 deterministic score。

## 10. Dialog 與 A11y

- `role=dialog`、`aria-modal=true`、`aria-labelledby`。
- 開啟後焦點進入 dialog；Tab／Shift+Tab 循環。
- Escape、close、backdrop 行為一致。
- 關閉後恢復 opener focus。
- 保存／恢復 body overflow 與 overscroll behavior。
- iOS rubber-band 不穿透背景。
- 事件長文保留換行，展開控制有 `aria-expanded`。

## 11. 四階閱讀模式（後續）

| 模式 | 內容 |
|---|---|
| 小白 | 白話健康度、名詞 tooltip、強化風險警語 |
| 一般 | 個股、Podcast、雙鏈與標籤 |
| 分析師 | source conflict、雙向證據、PIT 5／20／60 |
| Auditor | 三種時間、hash、品質折減、治理版本、audit |

所有模式讀取同一份 report，不得在前端重算或產生不同分數。

## 12. UI Release Checklist

- [ ] Flutter `analyze`／widget tests 通過；User App 與 Admin Web 使用不同入口、認證與導覽。
- [ ] 今日頁只組合同一 `analysis_as_of` 的 market／sector／topic／candidate Mart，日期不一致顯示 partial。
- [ ] 個股首屏只顯示健康度、白話摘要、籌碼狀態與風險；K 線及五角色明細預設收合。
- [ ] 健康度高／中／低具文字與 semantics，不只依賴顏色；分數明示不是獲利機率。
- [ ] 交易新增、更正、跨年年度損益、缺價與超賣錯誤路徑通過；Flutter 不重算正式損益。
- [ ] 使用者 A 無法讀寫使用者 B 的 trade、position、PnL 或 private artifact reference。
- [ ] Mobile／iPad／desktop 無水平 overflow。
- [ ] 所有主要控制 ≥44×44。
- [ ] K 線替代表格、keyboard、touch、Escape 通過。
- [ ] Modal focus trap、restore、scroll lock 通過。
- [ ] empty／unavailable／partial／stale／fallback 文案正確。
- [ ] blocked 不公開；null 不顯示 0。
- [ ] report history 日期與 provenance 同步。
- [ ] 實際色彩通過 WCAG AA。
- [ ] iOS Safari、Android Chrome、iPad Safari 實機通過。
- [ ] VoiceOver、TalkBack 完整路徑通過。
- [ ] raw payload、secret、敏感 URL、traceback 不出現在 DOM／network response。
- [ ] 資料營運中心九個分頁一次只顯示一個 panel，query-string deep link、鍵盤 tabs 與 responsive 導覽通過。
- [ ] 股票狀態、execution、DQ／quarantine 與 Mart 分析均以結構化表格呈現，沒有 raw JSON 主視圖。
- [ ] Prompt revision 的 draft／diff／activate／retire 與來源候選審查 gate 有 audit，保存不觸發 Job。
