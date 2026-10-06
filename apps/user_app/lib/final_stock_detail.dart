import 'package:flutter/material.dart';

import 'final_charts.dart';
import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalStockDetailPage extends StatefulWidget {
  const FinalStockDetailPage({required this.api, required this.symbol, super.key});

  final legacy.Api api;
  final String symbol;

  @override
  State<FinalStockDetailPage> createState() => _FinalStockDetailPageState();
}

class _FinalStockDetailPageState extends State<FinalStockDetailPage> {
  final values = <String, dynamic>{};
  final errors = <String>{};
  bool loading = true;
  bool klineLoading = false;
  bool klineRequested = false;

  Future<dynamic> safe(String key, String path) async {
    try {
      final value = await widget.api.get(path);
      values[key] = value;
      errors.remove(key);
      return value;
    } catch (_) {
      errors.add(key);
      return null;
    }
  }

  @override
  void initState() {
    super.initState();
    loadPrimary();
  }

  Future<void> loadPrimary() async {
    if (mounted) setState(() => loading = true);
    await Future.wait([
      safe(
        'health',
        '/api/v1/public/stock-health/${Uri.encodeComponent(widget.symbol)}',
      ),
      safe('positions', '/api/v1/me/journal/positions'),
      safe(
        'notes',
        '/api/v1/me/notes?symbol=${Uri.encodeQueryComponent(widget.symbol)}',
      ),
      safe(
        'events',
        '/api/v1/public/events/${Uri.encodeComponent(widget.symbol)}',
      ),
    ]);
    if (mounted) setState(() => loading = false);
  }

  Future<void> loadKline() async {
    if (klineRequested) return;
    setState(() {
      klineRequested = true;
      klineLoading = true;
    });
    await safe(
      'kline',
      '/api/v1/public/kline/${Uri.encodeComponent(widget.symbol)}',
    );
    if (mounted) setState(() => klineLoading = false);
  }

  List<dynamic> get positions => fvRows(values['positions'])
      .where((item) => fvText(fvMap(item)['symbol'], missing: '') == widget.symbol)
      .toList();

  Widget reasonColumn(String title, List<dynamic> items, IconData icon) =>
      fvPanel(
        padding: const EdgeInsets.all(13),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 18, color: fvTeal),
                const SizedBox(width: 6),
                Text(
                  title,
                  style: const TextStyle(
                    color: fvInk,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 9),
            if (items.isEmpty)
              const Text(
                '尚未就緒',
                style: TextStyle(color: fvMuted, fontSize: 12),
              )
            else
              for (final item in items.take(3))
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text(
                    '• ${fvText(item is Map ? (fvMap(item)['title'] ?? fvMap(item)['summary'] ?? fvMap(item)['reason']) : item)}',
                    style: const TextStyle(
                      color: fvInk,
                      fontSize: 12,
                      height: 1.35,
                    ),
                  ),
                ),
          ],
        ),
      );

  @override
  Widget build(BuildContext context) {
    final report = fvMap(values['health']);
    final reportData = fvMap(report['data']);
    final health = reportData.isNotEmpty ? reportData : report;
    final name = fvText(
      health['stock_name'] ?? health['name'],
      missing: widget.symbol,
    );
    final notes = fvRows(values['notes']);
    final events = fvRows(values['events']);
    final position = positions.isEmpty
        ? <String, dynamic>{}
        : fvMap(positions.first);
    final summary = health['plain_language_summary'] ?? health['summary'];
    final supports = fvRows(
      health['supports'] ?? health['why'] ?? health['reasons'],
    );
    final risks = fvRows(
      health['risks'] ?? health['watchouts'] ?? health['warnings'],
    );
    final dimensions = fvMap(
      health['dimensions'] ?? health['role_scores'] ?? health['scores'],
    );
    final chips = health['chips'] ?? health['institutional'] ?? health['positioning'];
    final evidence = fvMap(
      report['provenance'] ?? health['provenance'] ?? health['sources'],
    );

    return Scaffold(
      backgroundColor: fvCanvas,
      appBar: AppBar(
        backgroundColor: fvCanvas,
        surfaceTintColor: fvCanvas,
        elevation: 0,
        foregroundColor: fvInk,
        title: Text(
          '${widget.symbol} $name',
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: loadPrimary,
        child: ListView(
          key: const Key('final-stock-detail-scroll'),
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 40),
          children: [
            fvPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          name,
                          style: const TextStyle(
                            color: fvInk,
                            fontSize: 25,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      fvStatusPill(
                        report['data_status'] ??
                            health['data_status'] ??
                            (loading ? 'partial' : 'available'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(widget.symbol, style: const TextStyle(color: fvMuted)),
                  if (report['analysis_as_of'] != null ||
                      health['analysis_as_of'] != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      '資料日 ${fvText(report['analysis_as_of'] ?? health['analysis_as_of'])}',
                      style: const TextStyle(color: fvMuted, fontSize: 11),
                    ),
                  ],
                ],
              ),
            ),
            fvSectionTitle(context, '我的持股'),
            if (errors.contains('positions'))
              fvBoundedState('持股資料尚未取得')
            else if (position.isEmpty)
              fvBoundedState('目前無持股')
            else
              fvPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '持有 ${legacy.accountingNumber(position['shares'])} 股',
                      style: const TextStyle(
                        color: fvInk,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      '平均成本 ${legacy.accountingNumber(position['average_cost'], decimals: 2)} · 現價 ${legacy.accountingNumber(position['market_price'], decimals: 2, missing: '缺價')}',
                      style: const TextStyle(color: fvInk),
                    ),
                    Text(
                      '未實現損益 ${legacy.accountingNumber(position['unrealized_pnl'], missing: '資料不足')} · ${legacy.portfolioReturnLabel(position['unrealized_return'])}',
                      style: const TextStyle(color: fvInk),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      '估值日 ${fvText(position['valuation_date'])} · 行情日 ${fvText(position['price_date'])}',
                      style: const TextStyle(color: fvMuted, fontSize: 11),
                    ),
                  ],
                ),
              ),
            fvSectionTitle(context, '筆記與待追蹤'),
            if (errors.contains('notes'))
              fvBoundedState('筆記資料尚未取得')
            else if (notes.isEmpty)
              fvBoundedState('目前沒有這檔股票的筆記')
            else
              fvPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final item in notes.take(3))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 9),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              fvMap(item)['needs_follow_up'] == true
                                  ? Icons.flag_outlined
                                  : Icons.notes_outlined,
                              color: fvTeal,
                              size: 19,
                            ),
                            const SizedBox(width: 9),
                            Expanded(
                              child: Text(
                                fvText(
                                  fvMap(item)['body'] ??
                                      fvMap(item)['text'] ??
                                      fvMap(item)['content'],
                                  missing: '筆記內容不可用',
                                ),
                                style: const TextStyle(
                                  color: fvInk,
                                  height: 1.4,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            fvSectionTitle(context, '五面向健康度'),
            if (dimensions.isEmpty && health['mart_health_score'] == null)
              fvBoundedState('五面向健康度尚未就緒')
            else
              FvHealthBars(
                dimensions: dimensions,
                overall: health['mart_health_score'],
              ),
            fvSectionTitle(context, '白話摘要'),
            summary == null
                ? fvBoundedState('白話摘要尚未就緒；不會在開頁時自動呼叫 LLM')
                : fvPanel(
                    child: Text(
                      '$summary',
                      style: const TextStyle(color: fvInk, height: 1.55),
                    ),
                  ),
            fvSectionTitle(context, '為什麼／要注意什麼'),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: reasonColumn(
                    '支持',
                    supports,
                    Icons.check_circle_outline,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: reasonColumn(
                    '風險',
                    risks,
                    Icons.warning_amber_outlined,
                  ),
                ),
              ],
            ),
            fvSectionTitle(context, '籌碼與定位'),
            chips == null
                ? fvBoundedState('籌碼與定位資料尚未就緒')
                : fvPanel(
                    child: Text(
                      fvText(chips),
                      style: const TextStyle(color: fvInk, height: 1.45),
                    ),
                  ),
            fvSectionTitle(context, '公司事件'),
            if (errors.contains('events'))
              fvBoundedState('公司事件暫時無法使用')
            else if (events.isEmpty)
              fvBoundedState('目前沒有可發布事件')
            else
              fvPanel(
                child: Column(
                  children: [
                    for (final item in events.take(6))
                      Builder(builder: (context) {
                        final row = fvMap(item);
                        return ListTile(
                          contentPadding: EdgeInsets.zero,
                          dense: true,
                          leading:
                              const Icon(Icons.event_outlined, color: fvTeal),
                          title: Text(
                            fvText(
                              row['title'] ??
                                  row['event_type'] ??
                                  row['summary'],
                              missing: '事件',
                            ),
                          ),
                          subtitle: Text(
                            fvText(
                              row['event_date'] ??
                                  row['date'] ??
                                  row['published_at'],
                              missing: '日期未定',
                            ),
                          ),
                        );
                      }),
                  ],
                ),
              ),
            ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(horizontal: 4),
              title: const Text(
                '證據與來源',
                style: TextStyle(color: fvInk, fontWeight: FontWeight.w800),
              ),
              children: [
                if (evidence.isEmpty)
                  fvBoundedState('證據與來源尚未就緒')
                else
                  fvPanel(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final entry in evidence.entries)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Text(
                              '${entry.key}：${fvText(entry.value)}',
                              style: const TextStyle(
                                color: fvMuted,
                                fontSize: 12,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
              ],
            ),
            ExpansionTile(
              key: const Key('advanced-section'),
              tilePadding: const EdgeInsets.symmetric(horizontal: 4),
              onExpansionChanged: (expanded) {
                if (expanded) loadKline();
              },
              title: const Text(
                '進階資料',
                style: TextStyle(color: fvInk, fontWeight: FontWeight.w800),
              ),
              subtitle: const Text(
                'K 線、Fact Pack、specialist、CEO 與完整 provenance 依能力載入',
              ),
              children: [
                if (klineLoading)
                  fvBoundedState('K 線載入中')
                else if (klineRequested && errors.contains('kline'))
                  fvBoundedState('K 線暫時無法使用')
                else if (klineRequested && fvRows(values['kline']).isEmpty)
                  fvBoundedState('K 線資料尚未就緒')
                else if (klineRequested)
                  FvKlineChart(rows: fvRows(values['kline'])),
                fvBoundedState(
                  'Fact Pack、五 specialist 與 On-demand CEO 僅在 persisted artifact 可用時顯示。',
                ),
              ],
            ),
            const SizedBox(height: 14),
            const Text(
              '本頁提供研究資訊，不構成投資建議。資料可能為 partial、stale 或 unavailable，請以標示的資料日期與來源為準。',
              style: TextStyle(color: fvMuted, fontSize: 12, height: 1.45),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
