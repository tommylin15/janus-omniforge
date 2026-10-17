import 'dart:async';

import 'package:flutter/material.dart';

import 'final_charts.dart';
import 'final_perf.dart';
import 'final_analysis.dart';
import 'final_visual_common.dart';
import 'final_visual_series.dart';
import 'main.dart' as legacy;

int _usableVisualSeriesPoints(Map<String, dynamic> series) {
  // An explicit null marker is a gap, not a usable chart observation.
  final valid = fvRows(series['points'])
      .where((item) => fvChartNumber(fvMap(item)['value']) != null).length;
  if (series['usable_points'] == null) return valid;
  final declared = fvInt(series['usable_points']);
  return declared < valid ? declared : valid;
}

List<Map<String, dynamic>> _eventTimelineRows(List<dynamic> raw) {
  final uniqueIds = <String>{};
  final events = <Map<String, dynamic>>[];
  for (final item in raw) {
    final row = fvMap(item);
    final eventId = fvText(row['event_id'], missing: '');
    if (eventId.isNotEmpty && !uniqueIds.add(eventId)) continue;
    events.add(row);
  }
  // Published announcements first. Event/effective dates never masquerade
  // as a publication date and cannot be used to claim earlier knowledge.
  events.sort((a, b) => fvText(b['published_at'], missing: '')
      .compareTo(fvText(a['published_at'], missing: '')));
  return events.take(6).toList();
}

class FinalStockDetailPage extends StatefulWidget {
  const FinalStockDetailPage(
      {required this.api, required this.symbol, super.key});

  final legacy.Api api;
  final String symbol;

  @override
  State<FinalStockDetailPage> createState() => _FinalStockDetailPageState();
}

class _FinalStockDetailPageState extends State<FinalStockDetailPage>
    with WidgetsBindingObserver {
  final values = <String, dynamic>{};
  Timer? quoteTimer;
  bool foreground = true;
  final errors = <String>{};
  bool loading = true;
  bool klineLoading = false;
  bool klineRequested = false;
  int klineGeneration = 0;
  int chartDays = 66;
  bool candleChart = false;
  String? selectedVisual;
  final loadingVisual = <String>{};
  int primaryGeneration = 0;
  // Ignore responses from an earlier A→B→A navigation or an older refresh.
  int requestEpoch = 0;
  final requestVersions = <String, int>{};

  // Requests are bounded independently: one slow optional card never holds the page.
  Future<dynamic> safe(String key, String path) async {
    final requestedSymbol = widget.symbol;
    final requestedApi = widget.api;
    final epoch = requestEpoch;
    final version = (requestVersions[key] ?? 0) + 1;
    requestVersions[key] = version;
    bool current() => mounted && requestEpoch == epoch &&
        requestVersions[key] == version && widget.symbol == requestedSymbol &&
        identical(widget.api, requestedApi);
    try {
      final value = await requestedApi.get(path).timeout(const Duration(seconds: 9));
      if (current()) {
        setState(() {
          values[key] = value;
          errors.remove(key);
        });
      }
      return value;
    } catch (_) {
      if (current()) {
        setState(() => errors.add(key));
      }
      return null;
    }
  }

  bool get marketHours {
    final taipei = DateTime.now().toUtc().add(const Duration(hours: 8));
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 540 && minutes < 810;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    foreground = WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    loadPrimary();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _startQuoteTimer();
    });
  }

  @override
  void didUpdateWidget(covariant FinalStockDetailPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.symbol != widget.symbol || !identical(oldWidget.api, widget.api)) {
      quoteTimer?.cancel();
      requestEpoch++;
      requestVersions.clear();
      values.clear();
      errors.clear();
      klineRequested = false;
      klineLoading = false;
      chartDays = 22;
      selectedVisual = null;
      loadingVisual.clear();
      unawaited(loadPrimary());
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _startQuoteTimer();
      });
    }
  }

  void _startQuoteTimer() {
    quoteTimer?.cancel();
    if (foreground &&
        marketHours &&
        (ModalRoute.of(context)?.isCurrent ?? true)) {
      quoteTimer = Timer.periodic(const Duration(minutes: 1), (_) {
        if (!foreground ||
            !marketHours ||
            !(ModalRoute.of(context)?.isCurrent ?? true)) {
          quoteTimer?.cancel();
        } else {
          safe('header',
              '/api/v1/public/stock-header/${Uri.encodeComponent(widget.symbol)}');
          safe('quotes', '/api/v1/me/portfolio/quotes');
        }
      });
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground) {
      safe('header',
          '/api/v1/public/stock-header/${Uri.encodeComponent(widget.symbol)}');
      safe('quotes', '/api/v1/me/portfolio/quotes');
      _startQuoteTimer();
    } else {
      quoteTimer?.cancel();
    }
  }

  @override
  void dispose() {
    quoteTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<void> loadPrimary() async {
    final generation = ++primaryGeneration;
    final stopwatch = Stopwatch()..start();
    if (mounted) setState(() => loading = true);
    // All secondary requests are independent of the initial price/holdings view.
    unawaited(safe('baseline',
        '/api/v1/me/analysis/${Uri.encodeComponent(widget.symbol)}'));
    unawaited(Future.wait([
      safe('health', '/api/v1/public/stock-health/${Uri.encodeComponent(widget.symbol)}'),
      safe('notes', '/api/v1/me/notes?symbol=${Uri.encodeQueryComponent(widget.symbol)}'),
      safe('events', '/api/v1/public/events/${Uri.encodeComponent(widget.symbol)}'),
    ]));
    unawaited(loadKline());
    try {
      await Future.wait([
        safe('header', '/api/v1/public/stock-header/${Uri.encodeComponent(widget.symbol)}'),
        loadHoldings(),
      ]);
    } finally {
      stopwatch.stop();
      FinalPerf.recordCore('stock-detail', stopwatch.elapsed);
      if (mounted && generation == primaryGeneration) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> loadHoldings() async {
    final epoch = requestEpoch;
    final snapshot = await safe('quotes', '/api/v1/me/portfolio/snapshot');
    if (!mounted || epoch != requestEpoch) return;
    if (snapshot is Map && snapshot['positions'] is List) return;
    await Future.wait([
      safe('quotes', '/api/v1/me/portfolio/quotes'),
      safe('positions', '/api/v1/me/journal/positions'),
    ]);
  }

  Future<void> loadKline({bool force = false}) async {
    final requestedSymbol = widget.symbol;
    final epoch = requestEpoch;
    if (klineRequested && !force) return;
    if (!mounted) return;
    final generation = ++klineGeneration;
    setState(() {
      klineRequested = true;
      klineLoading = true;
    });
    final first = await safe('kline', '/api/v1/public/kline/${Uri.encodeComponent(widget.symbol)}');
    if (chartDays > 200 && first != null && mounted && generation == klineGeneration && epoch == requestEpoch && requestedSymbol == widget.symbol) {
      final older = await safe('kline-older', '/api/v1/public/kline/${Uri.encodeComponent(widget.symbol)}?limit=64&offset=200');
      if (older != null && mounted && generation == klineGeneration && epoch == requestEpoch && requestedSymbol == widget.symbol) {
        setState(() => values['kline'] = [...fvRows(first), ...fvRows(older)]);
      }
    }
    if (mounted && generation == klineGeneration && epoch == requestEpoch && requestedSymbol == widget.symbol) {
      setState(() => klineLoading = false);
    }
  }


  void _openExpandedChart() {
    final rows = fvRows(values['kline']);
    if (rows.isEmpty) return;
    showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog(
        insetPadding: const EdgeInsets.all(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: SizedBox(
            height: MediaQuery.sizeOf(dialogContext).height * .70,
            child: Column(
              children: [
                Row(children: [
                  const Expanded(child: Text('價格與量能 · 捏合縮放圖表',
                    style: TextStyle(color: fvInk, fontWeight: FontWeight.w800))),
                  IconButton(tooltip: '關閉圖表', onPressed: () => Navigator.pop(dialogContext),
                    icon: const Icon(Icons.close)),
                ]),
                Expanded(child: InteractiveViewer(
                  minScale: 1,
                  maxScale: 3,
                  child: SizedBox(
                    width: MediaQuery.sizeOf(dialogContext).width - 48,
                    child: FvKlineChart(rows: rows, maxPoints: chartDays, chartHeight: 280, candlesticks: candleChart),
                  ),
                )),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> openVisual(String metric) async {
    setState(() => selectedVisual = metric);
    if (!const {'pe', 'pb', 'yield', 'foreign', 'investment_trust', 'dealer', 'revenue', 'eps'}.contains(metric)) return;
    final key = 'visual-$metric';
    if ((values.containsKey(key) && !errors.contains(key)) || loadingVisual.contains(key)) return;
    setState(() => loadingVisual.add(key));
    final symbol = widget.symbol;
    final epoch = requestEpoch;
    await safe(key,
      '/api/v1/public/stocks/${Uri.encodeComponent(symbol)}/visual-series?metric=$metric&limit=120');
    if (mounted && epoch == requestEpoch && widget.symbol == symbol) {
      setState(() => loadingVisual.remove(key));
    }
  }

  void expandVisual(Map<String, dynamic> result, String label) {
    final points = fvRows(result['points']);
    if (_usableVisualSeriesPoints(result) < 2) return;
    showDialog<void>(context: context, builder: (ctx) => Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 28),
      child: Padding(padding: const EdgeInsets.all(12), child: Column(
        mainAxisSize: MainAxisSize.min, children: [
          Row(children: [
            Expanded(child: Text('$label · 捏合放大', style: const TextStyle(fontWeight: FontWeight.w800))),
            IconButton(tooltip: '關閉估值圖', icon: const Icon(Icons.close), onPressed: () => Navigator.pop(ctx)),
          ]),
          InteractiveViewer(minScale: 1, maxScale: 3, child: SizedBox(
            width: MediaQuery.sizeOf(ctx).width - 48,
            child: FvVisualSeriesChart(rows: points, label: label, unit: fvText(result['unit']), height: 270,
              bars: const {'foreign', 'investment_trust', 'dealer', 'revenue', 'eps'}.contains(result['metric'])))),
        ],
      )),
    ));
  }

  List<dynamic> get positions {
    final quotePayload = fvMap(values['quotes']);
    final source = quotePayload['positions'] is List
        ? quotePayload['positions'] as List
        : fvRows(values['positions']);
    return source
        .where((item) =>
            fvText(fvMap(item)['symbol'], missing: '') == widget.symbol)
        .toList();
  }

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
    final baseline = fvMap(values['baseline']);
    final baselineRoles = fvRows(baseline['specialists']);
    final report = fvMap(values['health']);
    final reportData = fvMap(report['data']);
    final health = baselineRoles.isNotEmpty
        ? <String, dynamic>{}
        : reportData.isNotEmpty ? reportData : report;
    final header = fvMap(values['header']);
    final name = fvText(
      header['stock_name'] ?? health['stock_name'] ?? health['name'],
      missing: widget.symbol,
    );
    final notes = fvRows(values['notes']);
    final events = fvRows(values['events']);
    final position =
        positions.isEmpty ? <String, dynamic>{} : fvMap(positions.first);
    final usableRoles = baselineRoles.map(fvMap).where((r) => r['baseline_status'] == 'available');
    final summary = baselineRoles.isEmpty
        ? health['plain_language_summary'] ?? health['summary']
        : usableRoles.isEmpty
            ? '五分析師基準仍有資料缺口；目前不提供方向性結論。可於進階資料查看各角色來源與缺值。'
            : fvText(usableRoles.first['plain_language']);
    final supports = fvRows(
      health['supports'] ?? health['why'] ?? health['reasons'],
    );
    final risks = fvRows(
      health['risks'] ?? health['watchouts'] ?? health['warnings'],
    );
    final dimensions = fvMap(
      health['dimensions'] ?? health['role_scores'] ?? health['scores'],
    );
    final chips =
        health['chips'] ?? health['institutional'] ?? health['positioning'];
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
                  const SizedBox(height: 8),
                  Text(
                    legacy.accountingNumber(header['close'], decimals: 2, missing: '尚未取得'),
                    key: const Key('stock-price-value'),
                    style: const TextStyle(color: fvInk, fontSize: 30, fontWeight: FontWeight.w800),
                  ),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(
                        '${header['price_source'] == 'twse_mis' ? '盤中最新價' : '正式收盤價'} · 行情日 ${fvText(header['trade_date'])}',
                        style: const TextStyle(color: fvMuted, fontSize: 12),
                      ),
                      if (header['change'] != null)
                        Text(
                          '${fvNumber(header['change']) != null && fvNumber(header['change'])! > 0 ? '▲ +' : fvNumber(header['change']) != null && fvNumber(header['change'])! < 0 ? '▼ ' : ''}${legacy.accountingNumber(header['change'], decimals: 2)} (${fvSignedPercent(header['change_percent'])})',
                          key: const Key('stock-price-change'),
                          style: TextStyle(
                            color: fvSignedColor(header['change']),
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                    ],
                  ),
                  if (errors.contains('header'))
                    const Text('報價更新失敗，顯示上次有效資料',
                        style: TextStyle(color: fvMuted, fontSize: 11)),
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
            if (fvMap(values['quotes'])['positions'] is! List && values['positions'] is! List)
              fvBoundedState(loading ? '持股資料載入中' : '持股資料尚未取得')
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
                      key: const Key('stock-unrealized-pnl'),
                      style: TextStyle(
                        color: fvSignedColor(position['unrealized_pnl']),
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      '估值日 ${fvText(position['valuation_date'])} · 行情日 ${fvText(position['price_date'])}',
                      style: const TextStyle(color: fvMuted, fontSize: 11),
                    ),
                  ],
                ),
              ),
            fvSectionTitle(context, '價格與量能'),
            Row(
              children: [
                const Icon(Icons.candlestick_chart_outlined, color: fvTeal, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Wrap(
                    spacing: 6,
                    children: [
                      for (final period in const [22, 66, 132, 264])
                        ChoiceChip(
                          label: Text(const {22: '近1月', 66: '近3月', 132: '近6月', 264: '近12月'}[period]!),
                          selected: chartDays == period,
                          onSelected: (_) {
                            setState(() => chartDays = period);
                            if (period > 200) loadKline(force: true);
                          },
                        ),
                    ],
                  ),
                ),
                if (fvRows(values['kline']).isNotEmpty)
                  IconButton(
                    key: const Key('stock-chart-expand'),
                    tooltip: '放大圖表',
                    onPressed: _openExpandedChart,
                    icon: const Icon(Icons.open_in_full, color: fvTeal),
                  ),
              ],
            ),
            Wrap(spacing: 6, children: [
              ChoiceChip(label: const Text('收盤折線'), selected: !candleChart,
                onSelected: (_) => setState(() => candleChart = false)),
              ChoiceChip(label: const Text('日 K'), selected: candleChart,
                onSelected: (_) => setState(() => candleChart = true)),
            ]),
            if (klineLoading && fvRows(values['kline']).isEmpty)
              fvBoundedState('價格圖載入中；其餘個股資訊可先查看', icon: Icons.show_chart)
            else if (errors.contains('kline') && fvRows(values['kline']).isEmpty)
              fvPanel(child: Row(children: [
                const Expanded(child: Text('價格圖暫時無法使用')),
                TextButton(onPressed: () => loadKline(force: true), child: const Text('重試')),
              ]))
            else if (fvRows(values['kline']).isEmpty)
              fvBoundedState('尚無可繪製的正式行情，不顯示示意圖')
            else ...[
              FvKlineChart(rows: fvRows(values['kline']), maxPoints: chartDays, candlesticks: candleChart),
              if (errors.contains('kline'))
                const Text('行情更新失敗，保留上次有效圖表',
                    style: TextStyle(color: fvMuted, fontSize: 11)),
            ],
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
            if (report['model_validation_status'] == 'validated') ...[
            fvSectionTitle(context, '五面向健康度'),
            if (dimensions.isEmpty && health['mart_health_score'] == null)
              fvBoundedState('五面向健康度尚未就緒')
            else
              FvHealthBars(
                dimensions: dimensions,
                overall: health['mart_health_score'],
              ),
            fvSectionTitle(context, '白話摘要'),
            if (baselineRoles.isNotEmpty)
              Text('基準分析日 ${fvText(baseline['analysis_as_of'])} · ${baseline['freshness'] == 'stale' ? '資料過期' : '已保存'}；完整五角色見進階資料',
                  style: const TextStyle(color: fvMuted, fontSize: 12)),
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
            ],
            fvSectionTitle(context, '圖表總覽'),
            fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('選擇想看的趨勢', style: TextStyle(fontWeight: FontWeight.w800, color: fvInk)),
              const SizedBox(height: 9),
              Wrap(spacing: 7, runSpacing: 7, children: [
                for (final entry in const {'pe': '本益比', 'pb': '股價淨值比',
                    'yield': '殖利率', 'revenue': '月營收',
                    'eps': 'EPS', 'foreign': '外資', 'investment_trust': '投信',
                    'dealer': '自營商', 'events': '事件'}.entries)
                  ChoiceChip(
                    key: Key('visual-tab-${entry.key}'),
                    label: Text(entry.value),
                    selected: selectedVisual == entry.key,
                    onSelected: (_) => openVisual(entry.key),
                  ),
              ]),
              const SizedBox(height: 7),
              const Text('僅呈現已發布資料。缺少可比較歷史時明確標示。',
                  style: TextStyle(color: fvMuted, fontSize: 11)),
            ])),
            if (selectedVisual != null) ...[
              if (const {'pe', 'pb', 'yield', 'foreign', 'investment_trust', 'dealer', 'revenue', 'eps'}.contains(selectedVisual)) ...[
                if (loadingVisual.contains('visual-$selectedVisual'))
                  fvBoundedState('圖表載入中；其餘資訊可繼續使用', icon: Icons.query_stats)
                else if (errors.contains('visual-$selectedVisual'))
                  fvPanel(child: Row(children: [
                    const Expanded(child: Text('圖表讀取失敗')),
                    TextButton(onPressed: () => openVisual(selectedVisual!), child: const Text('重試')),
                  ]))
                else Builder(builder: (context) {
                  final result = fvMap(values['visual-$selectedVisual']);
                  final points = fvRows(result['points']);
                  final label = const {'pe': '本益比', 'pb': '股價淨值比', 'yield': '殖利率',
                    'foreign': '外資買賣超', 'investment_trust': '投信買賣超',
                    'dealer': '自營商買賣超', 'revenue': '月營收', 'eps': '單季 EPS'}[selectedVisual]!;
                  if (_usableVisualSeriesPoints(result) < 2) {
                    return fvBoundedState('歷史資料不足：${fvText(result['missing_reason'], missing: '尚未就緒')}');
                  }
                  return Column(children: [
                    Row(children: [
                      Expanded(child: Text('資料日 ${fvText(result['data_as_of'])} · ${fvText(result['data_status'])}',
                        style: const TextStyle(color: fvMuted, fontSize: 11))),
                      IconButton(key: const Key('valuation-chart-expand'), tooltip: '放大估值圖',
                        onPressed: () => expandVisual(result, label),
                        icon: const Icon(Icons.open_in_full, color: fvTeal)),
                    ]),
                    if (selectedVisual == 'revenue') Builder(builder: (context) {
                      final yoy = fvMap(result['revenue_yoy']);
                      final change = fvNumber(yoy['percent']);
                      return Align(
                        alignment: Alignment.centerLeft,
                        child: Text(
                          change == null
                              ? '營收年增率：去年同月資料不足；月營收仍可參考'
                              : '營收年增率 ${change > 0 ? '+' : ''}${change.toStringAsFixed(2)}% · 去年同月 ${fvText(yoy['comparison_period'])}',
                          style: TextStyle(
                            color: change == null ? fvMuted : fvSignedColor(change),
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      );
                    }),
                    FvVisualSeriesChart(rows: points, label: label, unit: fvText(result['unit']),
                      bars: const {'foreign', 'investment_trust', 'dealer', 'revenue', 'eps'}.contains(selectedVisual)),
                    Text('來源：${fvRows(result['source_ids']).join('、')}',
                      style: const TextStyle(color: fvMuted, fontSize: 11)),
                  ]);
                }),
              ] else
                fvBoundedState(selectedVisual == 'events'
                  ? '公司事件請參考下方官方事件時間軸。'
                  : '尚無通過期別、來源和可比性驗證的歷史序列。'),
            ],
            fvSectionTitle(context, '籌碼與定位'),
            chips == null
                ? fvBoundedState('籌碼與定位資料尚未就緒')
                : fvPanel(
                    child: Text(
                      fvText(chips),
                      style: const TextStyle(color: fvInk, height: 1.45),
                    ),
                  ),
            fvSectionTitle(context, '公司事件時間軸'),
            if (errors.contains('events'))
              fvBoundedState('公司事件暫時無法使用')
            else if (events.isEmpty)
              fvBoundedState('目前沒有可發布事件')
            else
              fvPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('依正式公告時間排序；日期不明者置後，不推測事件利多或利空。',
                        style: TextStyle(color: fvMuted, fontSize: 11)),
                    const SizedBox(height: 10),
                    for (final row in _eventTimelineRows(events))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Padding(
                              padding: EdgeInsets.only(top: 3, right: 10),
                              child: Icon(Icons.radio_button_checked, color: fvTeal, size: 17),
                            ),
                            Expanded(child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(fvText(row['title'] ?? row['event_type'] ?? row['summary'],
                                      missing: '事件'),
                                    style: const TextStyle(color: fvInk,
                                        fontWeight: FontWeight.w700)),
                                Text(row['published_at'] != null
                                    ? '公告：${fvText(row['published_at'])}'
                                    : '公告時間未確認',
                                    style: const TextStyle(color: fvMuted, fontSize: 11)),
                                if (row['effective_date'] != null)
                                  Text('生效：${fvText(row['effective_date'])}',
                                      style: const TextStyle(color: fvMuted, fontSize: 11)),
                                if (row['published_at'] == null &&
                                    (row['event_date'] ?? row['date']) != null)
                                  Text('事件日：${fvText(row['event_date'] ?? row['date'])}',
                                      style: const TextStyle(color: fvMuted, fontSize: 11)),
                                if (row['source_id'] != null)
                                  Text('來源：${fvText(row['source_id'])}',
                                      style: const TextStyle(color: fvMuted, fontSize: 11)),
                              ],
                            )),
                          ],
                        ),
                      ),
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
              title: const Text(
                '進階資料',
                style: TextStyle(color: fvInk, fontWeight: FontWeight.w800),
              ),
              subtitle: const Text(
                '完整 specialist、CEO 與 provenance 依能力載入；價量圖已在上方',
              ),
              children: [
                FinalAnalysisPanel(widget.api, widget.symbol),
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
