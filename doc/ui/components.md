# Janus UI — 元件契約

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

### MetricsGrid

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

- `TradingJournalForm` 使用 Material 3 dropdown／segmented control 選擇買進、賣出、現金股利或股票股利，搭配日期選擇器、股票 autocomplete 與依類型顯示的十進位欄位；送出前顯示交易摘要，成功後顯示 ledger event ID。
- 賣出股數大於可用持股時由 API 拒絕，UI 保留輸入並顯示欄位級錯誤；前端預檢不能取代後端約束。
- `PnLSummary` 分開顯示已實現與未實現損益，並標示估值日期、成本法與缺價筆數；null 不顯示為 0。
- 刪除／修正需二次確認並說明會建立 reversal／replacement；成功後重新讀取已持久化 ledger／Mart，不在 Flutter 本地重算正式損益。

### NoteEditor／ChatRoom

- `NoteEditor` 使用平台原生 multiline text field、可選 symbol／trade 關聯與待追蹤 toggle；儲存後顯示 revision ID，不加入富文字編輯器或附件系統。
- `ChatRoom` 以 runtime／model selector 建立 thread；切換只允許新建／fork。訊息 delta、item、tool、approval、完成、錯誤與 citation event 以 event ID／seq 去重，item 依 item ID 更新；顯示 Cloud Run cold start／reconnect，離頁可取消，重連只從 last event ID 接續。
- `DataSourcePicker` 顯示 Janus public／private context 與核准外部來源的 as-of date、provenance、owner scope、quota；私人資料預設未選取。`McpSkillPanel` 顯示 Cloud Run stdio／remote HTTP/SSE、tool scope、skill revision／required tools，不提供本地路徑或任意 executable 上傳。
- `AgentTimeline` 以一般 message、Codex turn／item、MCP tool 與 approval card 顯示統一 AgentEvent；approval 顯示 Cloud Run sandbox 的具體操作、範圍與到期，禁止用單一全域「永遠允許」取代 request-bound decision。
- citation 顯示標題、來源、查詢時間與可點擊連結；Gemini Google Search grounding suggestion／attribution 依供應者條款呈現，不把搜尋片段冒充 Janus 已驗證事實。
