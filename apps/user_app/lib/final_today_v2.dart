import 'dart:async';

import 'package:flutter/material.dart';

import 'final_perf.dart';
import 'stock_order_book.dart';
import 'final_visual_series.dart';
import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalTodayPage extends StatefulWidget {
  const FinalTodayPage(this.api, {this.onOpenStock, this.active = true, super.key});

  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;
  final bool active;

  @override
  State<FinalTodayPage> createState() => _FinalTodayPageState();
}

class _FinalTodayPageState extends State<FinalTodayPage> with WidgetsBindingObserver {
  late Future<dynamic> market;
  late Future<dynamic> marketFlows;
  late Future<dynamic> brief;
  late Future<dynamic> personal;
  late Future<dynamic> ownerQuotes;
  Future<dynamic>? stockMinutes;
  Future<dynamic>? stockOrderBook;
  String? _bookSymbol;
  String? selectedHolding;
  bool showOrderBook = false;
  dynamic lastGoodOwnerQuotes;
  Timer? marketTimer;
  bool foreground = true;
  final Set<String> _backfillAttemptKeys = <String>{};
  final Set<String> _backfillInFlight = <String>{};
  final Map<String, String> _backfillStatus = <String, String>{};
  final Map<String, DateTime> _manualBackfillAt = <String, DateTime>{};
  int historyDays = 20;
  int todayTab = 0; // 0: live, 1: long-horizon
  bool researchLoaded = false;
  dynamic lastGoodMarket;
  bool marketBusy = false;
  int marketGeneration = 0;
  static const marketColdTimeout = Duration(seconds: 24);

  bool get marketHours {
    final taipei = DateTime.now().toUtc().add(const Duration(hours: 8));
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 540 && minutes < 810;
  }

  bool get marketActive =>
      widget.active && foreground && todayTab == 0 &&
      (ModalRoute.of(context)?.isCurrent ?? true);

  @override
  void initState() {
    super.initState();
    // IndexedStack creates every tab up front. Hidden tabs must not trigger
    // an upstream quote request until the user actually selects this page.
    market = widget.active ? _readCoreMarket() : Future<dynamic>.value(null);
    // Long-horizon research is requested only when its tab becomes visible.
    marketFlows = Future<dynamic>.value(null);
    brief = Future<dynamic>.value(null);
    personal = Future<dynamic>.value(null);
    ownerQuotes = widget.active
        ? market.then((_) => _loadOwnerQuotes(onDemandBackfill: true))
        : Future<dynamic>.value(null);
    WidgetsBinding.instance.addObserver(this);
    foreground = WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _startMarketTimer();
        _requestHistoricalGapFill('TAIEX');
      }
    });
  }


  void _requestHistoricalGapFill(String symbol, {bool manual = false}) {
    // Shioaji history is demanded on entry, resume, stock selection or
    // explicit user retry, never by the 60s quote timer. PG still limits 3/day
    // and enforces its cross-reader 30-minute cooldown.
    if (!widget.active || !foreground || todayTab != 0) return;
    final taipei = DateTime.now().toUtc().add(const Duration(hours: 8));
    final minute = taipei.hour * 60 + taipei.minute;
    if (taipei.weekday > 5 || minute < 560) return;
    final day = '${taipei.year}-${taipei.month}-${taipei.day}';
    final slot = ((minute - 540) ~/ 30).clamp(0, 9);
    if (_backfillInFlight.contains(symbol)) return;
    final key = '$day/$symbol/$slot';
    if (manual) {
      // A visible user's retry is still gated by the existing PostgreSQL
      // 30-minute cooldown and daily quota. Prevent repeated taps locally.
      final now = DateTime.now();
      final last = _manualBackfillAt[symbol];
      if (last != null && now.difference(last) < const Duration(minutes: 5)) return;
      _manualBackfillAt[symbol] = now;
    } else if (!_backfillAttemptKeys.add(key)) {
      return;
    }
    _backfillAttemptKeys.add(key);
    _fetchHistoricalGapFill(symbol);
  }

  Future<void> _fetchHistoricalGapFill(String symbol) async {
    if (!mounted || !widget.active) return;
    setState(() { _backfillInFlight.add(symbol); });
    try {
      final response = fvMap(await widget.api.post(
          '/api/v1/me/market/minute-backfill', {'symbol': symbol})
          .timeout(const Duration(seconds: 25)));
      if (!mounted || !widget.active) return;
      final status = fvText(response['status'], missing: 'unavailable');
      setState(() {
        _backfillStatus[symbol] = status;
        if (symbol == 'TAIEX' && (status == 'available' || status == 'cached_or_throttled')) {
          market = _loadMarketWithoutPerf();
        } else if (symbol == selectedHolding &&
            (status == 'available' || status == 'cached_or_throttled')) {
          stockMinutes = _read('/api/v1/me/portfolio/intraday?symbol=$symbol');
        }
      });
    } catch (_) {
      if (mounted) setState(() { _backfillStatus[symbol] = 'unavailable'; });
    } finally {
      if (mounted) setState(() { _backfillInFlight.remove(symbol); });
    }
  }

  Widget _backfillCaption(String symbol) {
    final running = _backfillInFlight.contains(symbol);
    final status = _backfillStatus[symbol];
    final recentManual = _manualBackfillAt[symbol];
    final manualCooling = recentManual != null &&
        DateTime.now().difference(recentManual) < const Duration(minutes: 5);
    if (!running && status == null) return const SizedBox.shrink();
    final message = running ? '正在查詢今日缺漏的歷史 1 分 K（非即時行情）…'
        : status == 'available' ? '已讀回歷史 1 分 K，與即時觀測合併顯示'
        : status == 'cached_or_throttled' ? '使用已保存分鐘資料；補收額度未開放時缺口可能保留'
        : '歷史 K 棒暫不可用，保留實際觀測點與缺口';
    return Padding(
      padding: const EdgeInsets.only(top: 3),
      child: Row(children: [
        Expanded(child: Text(message, key: Key('today-backfill-status-$symbol'),
            style: const TextStyle(color: fvMuted, fontSize: 11))),
        if (!running && marketHours)
          TextButton(
            key: Key('today-backfill-retry-$symbol'),
            onPressed: manualCooling
                ? null : () => _requestHistoricalGapFill(symbol, manual: true),
            child: Text(manualCooling ? '稍後重試' : '重查缺口',
                style: const TextStyle(fontSize: 12)),
          ),
      ]),
    );
  }

  void _loadResearch({bool refresh = false}) {
    if (!widget.active || (researchLoaded && !refresh)) return;
    researchLoaded = true;
    marketFlows = _read('/api/v1/public/market-leverage-flow',
        timeout: const Duration(seconds: 28));
    brief = _read('/api/v1/public/daily-brief');
    personal = _read('/api/v1/me/today-relevant');
  }

  void _switchTodayTab(int next) {
    if (next == todayTab) return;
    marketTimer?.cancel();
    setState(() {
      todayTab = next;
      if (next == 1) {
        _loadResearch();
      } else {
        market = _loadMarketWithoutPerf();
        ownerQuotes = market.then(
            (_) => _loadOwnerQuotes(onDemandBackfill: true));
      }
    });
    if (next == 0) {
      _startMarketTimer();
      _requestHistoricalGapFill('TAIEX');
    }
  }

  void _startMarketTimer() {
    marketTimer?.cancel();
    if (marketActive && marketHours) {
      marketTimer = Timer.periodic(const Duration(minutes: 1), (_) {
        if (!marketActive || !marketHours) {
          marketTimer?.cancel();
        } else {
          if (!marketBusy) setState(() {
            market = _loadMarketWithoutPerf();
            ownerQuotes = market.then((_) => _loadOwnerQuotes());
          });
        }
      });
    }
  }

  Future<dynamic> _loadMarketWithoutPerf() async {
    final generation = ++marketGeneration;
    marketBusy = true;
    try {
      final result = await _read('/api/v1/public/market-home', timeout: marketColdTimeout);
      if (mounted && generation == marketGeneration && result is Map && result['sections'] is Map) lastGoodMarket = result;
      return result;
    } finally {
      if (generation == marketGeneration) marketBusy = false;
    }
  }

  @override
  void didUpdateWidget(FinalTodayPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.api, widget.api)) {
      researchLoaded = false;
      lastGoodMarket = null;
      market = widget.active ? _readCoreMarket() : Future<dynamic>.value(null);
      marketFlows = Future<dynamic>.value(null);
      brief = Future<dynamic>.value(null);
      personal = Future<dynamic>.value(null);
      if (todayTab == 1) _loadResearch();
      ownerQuotes = widget.active
          ? market.then((_) => _loadOwnerQuotes(onDemandBackfill: true))
          : Future<dynamic>.value(null);
      }
    if (oldWidget.active != widget.active) {
      if (widget.active) {
        setState(() {
          market = _loadMarketWithoutPerf();
          if (todayTab == 1) _loadResearch();
          if (todayTab == 0) {
            ownerQuotes = market.then(
                (_) => _loadOwnerQuotes(onDemandBackfill: true));
          }
        });
        _startMarketTimer();
        if (todayTab == 0) _requestHistoricalGapFill('TAIEX');
      } else {
        marketTimer?.cancel();
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground) {
      if (widget.active) {
        setState(() {
          market = _loadMarketWithoutPerf();
          if (todayTab == 1 && researchLoaded) {
            marketFlows = _read('/api/v1/public/market-leverage-flow',
                timeout: const Duration(seconds: 28));
          } else if (todayTab == 0) {
            ownerQuotes = market.then(
                (_) => _loadOwnerQuotes(onDemandBackfill: true));
          }
        });
        _startMarketTimer();
        if (todayTab == 0) _requestHistoricalGapFill('TAIEX');
      }
    } else {
      marketTimer?.cancel();
    }
  }

  @override
  void dispose() {
    marketTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<dynamic> _readCoreMarket() async {
    final stopwatch = Stopwatch()..start();
    try {
      return await _loadMarketWithoutPerf();
    } finally {
      stopwatch.stop();
      FinalPerf.recordCore('today', stopwatch.elapsed);
    }
  }

  Future<dynamic> _read(String path,
      {Duration timeout = const Duration(seconds: 9)}) async {
    try {
      return await widget.api.get(path).timeout(timeout);
    } catch (_) {
      return null;
    }
  }

  Future<dynamic> _loadOwnerQuotes({bool onDemandBackfill = false}) async {
    final result = await _read('/api/v1/me/portfolio/quotes',
        timeout: const Duration(seconds: 24));
    if (!mounted || !widget.active || result is! Map) return result;
    if (result['positions'] is List) {
      lastGoodOwnerQuotes = result;
      final positions = fvRows(result['positions']).map(fvMap)
          .where((row) => row['currency'] == 'TWD' && row['symbol'] != null)
          .toList();
      // The default chart follows an ordinary share, not whichever ETF the
      // portfolio endpoint happens to return first.
      final ordinary = positions.where((row) => !_isEtf(row)).toList();
      if (selectedHolding == null ||
          !positions.any((row) => row['symbol'] == selectedHolding)) {
        selectedHolding = ordinary.isNotEmpty ? '${ordinary.first['symbol']}' :
            (positions.isNotEmpty ? '${positions.first['symbol']}' : null);
      }
      if (selectedHolding != null) {
        stockMinutes = _read(
          '/api/v1/me/portfolio/intraday?symbol=$selectedHolding');
        if (showOrderBook) _loadSelectedOrderBook(selectedHolding!);
        if (onDemandBackfill) _requestHistoricalGapFill(selectedHolding!);
      }
    }
    return result;
  }

  String _freshness(Map<String, dynamic> section) {
    final coverage = fvMap(section['coverage']);
    final parts = <String>[];
    if (section['as_of'] != null) parts.add('資料日 ${section['as_of']}');
    if (section['freshness_days'] != null) {
      final days = fvInt(section['freshness_days']);
      parts.add(days == 0 ? '最新交易日' : '$days 天前');
    }
    if (coverage['received_symbols'] != null && coverage['requested_symbols'] != null) {
      parts.add('涵蓋 ${coverage['received_symbols']}/${coverage['requested_symbols']} 檔');
    }
    return parts.join(' · ');
  }

  String _value(Map<String, dynamic> section) {
    final data = fvMap(section['data']);
    final value = data['close'] ?? data['index'] ?? data['value'];
    return value == null ? '資料尚未取得' : legacy.accountingNumber(value, decimals: 2);
  }

  Widget _benchmark(String label, IconData icon, dynamic raw) {
    final section = fvMap(raw);
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(icon, color: fvTeal, size: 19),
              const SizedBox(width: 7),
              Expanded(
                child: Text(label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
              ),
            ]),
            const SizedBox(height: 9),
            Text(_value(section),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: fvInk, fontSize: 25, fontWeight: FontWeight.w800)),
            const SizedBox(height: 7),
            Text(
              _freshness(section).isEmpty
                  ? legacy.uiLabel(section['status'] ?? 'partial')
                  : _freshness(section),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: fvMuted, fontSize: 10.5, height: 1.25),
            ),
          ],
        ),
      ),
    );
  }


  double? _taiexPreviousClose(List<dynamic> observed, List<dynamic> history) {
    // Benchmark history is already filtered for source and provenance in Core.
    // Never derive the daily zero level from the first minute observation.
    final sampleDays = observed.map((raw) {
      final value = DateTime.tryParse(fvText(fvMap(raw)['date'], missing: ''));
      return value?.toUtc().add(const Duration(hours: 8));
    }).whereType<DateTime>().toList()..sort();
    final reference = sampleDays.isEmpty
        ? DateTime.now().toUtc().add(const Duration(hours: 8))
        : sampleDays.last;
    final day = DateTime.utc(reference.year, reference.month, reference.day);
    final eligible = history.map(fvMap).where((row) {
      final date = DateTime.tryParse(fvText(row['date'], missing: ''));
      final close = fvNumber(row['value']);
      return date != null && date.isBefore(day) &&
          day.difference(date).inDays <= 7 &&
          close != null && close.isFinite && close > 0;
    }).toList()..sort((a, b) =>
      fvText(b['date']).compareTo(fvText(a['date'])));
    return eligible.isEmpty ? null : fvNumber(eligible.first['value']);
  }

  Widget _taiexTrend(dynamic raw, {bool intradayOnly = true}) {
    final section = fvMap(raw);
    final data = fvMap(section['data']);
    final history = fvRows(data['history_points']);
    final intraday = fvRows(data['intraday_points']);
    final previousClose = _taiexPreviousClose(intraday, history);
    // No provisional intraday quote, partial period, or sample placeholder
    // may be spliced into this official closing-price chart.
    final usable = history.where((item) {
      final value = fvNumber(fvMap(item)['value']);
      return value != null && value.isFinite && value > 0;
    }).toList();
    // The fixed clock frame renders even with zero/minimal observations.
    final shown = usable.length <= historyDays
        ? usable : usable.sublist(usable.length - historyDays);
    final asOf = fvText(data['history_as_of']);
    final sources = fvRows(data['history_source_ids']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.only(left: 4, right: 2, bottom: 4),
        child: Row(children: [
          const Icon(Icons.show_chart, color: fvTeal, size: 19),
          const SizedBox(width: 7),
          const Expanded(child: Text('加權指數走勢',
              style: TextStyle(color: fvInk, fontWeight: FontWeight.w800,
                  fontSize: 17))),
          IconButton(
            key: const Key('today-taiex-expand'),
            tooltip: '放大加權指數走勢',
            icon: const Icon(Icons.open_in_full, color: fvTeal),
            onPressed: () => showDialog<void>(context: context,
              builder: (dialogContext) => Dialog(
                insetPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 30),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Row(children: [
                      Expanded(child: Text(intradayOnly
                          ? '加權指數 · 今日分鐘觀測' : '加權指數 · 官方收盤走勢',
                        style: TextStyle(color: fvInk, fontWeight: FontWeight.w800))),
                      IconButton(icon: const Icon(Icons.close),
                        tooltip: '關閉大盤走勢', onPressed: () => Navigator.pop(dialogContext)),
                    ]),
                    InteractiveViewer(
                      minScale: 1, maxScale: 3,
                      child: intradayOnly
                          ? FvIntradayProgressChart(
                              rows: intraday, label: '加權指數 · 盤中',
                              unit: '點', height: 235, previousClose: previousClose)
                          : FvVisualSeriesChart(
                              rows: usable, label: '加權指數 · 收盤',
                              unit: '點', height: 235, dailyTable: true,
                              showTable: false),
                    ),
                  ]),
                ),
              )),
          ),
        ]),
      ),
      if (!intradayOnly)
        Material(color: Colors.transparent, child: Wrap(spacing: 5, children: [
          for (final days in const [5, 20, 30])
            ChoiceChip(
              key: Key('today-trend-$days'),
              visualDensity: VisualDensity.compact,
              label: Text(days == 5 ? '近5日' : days == 20 ? '近20日' : '近30日'),
              selected: historyDays == days,
              onSelected: (_) => setState(() => historyDays = days),
            ),
        ])),
      if (intradayOnly)
        FvIntradayProgressChart(rows: intraday, label: '加權指數 · 盤中',
            unit: '點', height: 190, previousClose: previousClose)
      else ...[
        FvVisualSeriesChart(rows: shown, label: '加權指數 · 官方收盤',
            unit: '點', height: 160, dailyTable: true, showTable: false),
        Align(alignment: Alignment.centerRight, child: TextButton.icon(
          key: const Key('today-longterm-history-details'),
          icon: const Icon(Icons.list_alt, size: 17),
          label: const Text('查看收盤明細'),
          onPressed: shown.isEmpty ? null : () => showModalBottomSheet<void>(
            context: context, isScrollControlled: true,
            builder: (sheetContext) => SafeArea(child: SizedBox(
              height: MediaQuery.sizeOf(sheetContext).height * 0.7,
              child: Column(children: [
                Row(children: [
                  const Expanded(child: Padding(
                    padding: EdgeInsets.only(left: 16),
                    child: Text('加權指數 · 官方收盤明細',
                        style: TextStyle(color: fvInk, fontSize: 18,
                            fontWeight: FontWeight.w800)),
                  )),
                  IconButton(
                    icon: const Icon(Icons.close),
                    tooltip: '關閉收盤明細',
                    onPressed: () => Navigator.pop(sheetContext)),
                ]),
                Expanded(child: ListView.builder(
                  itemCount: shown.length,
                  itemBuilder: (context, index) {
                    final row = fvMap(shown[shown.length - index - 1]);
                    return ListTile(
                      dense: true,
                      title: Text(fvText(row['date'])),
                      trailing: Text(
                        '${legacy.accountingNumber(row['value'], decimals: 2)} 點',
                        style: const TextStyle(fontWeight: FontWeight.w800)),
                    );
                  },
                )),
              ]),
            )),
          ),
        )),
      ],
      Padding(
        padding: const EdgeInsets.fromLTRB(5, 3, 5, 12),
        child: Text('正式收盤截至 $asOf · 來源 ${sources.isEmpty ? '待查' : sources.join('、')}'
            ' · 盤中資料獨立顯示，不計入正式日收盤',
            style: const TextStyle(fontSize: 11, color: fvMuted)),
      ),
    ]);
  }

  String _billions(Object? raw, {double divisor = 100000000}) {
    final value = fvNumber(raw);
    if (value == null || !value.isFinite) return '—';
    return legacy.accountingNumber(value / divisor, decimals: 2);
  }

  Widget _leverageFlow() => FutureBuilder<dynamic>(
    future: marketFlows,
    builder: (context, snapshot) {
      final root = fvMap(snapshot.data);
      final margin = fvMap(root['margin']);
      final flows = fvMap(root['institutional']);
      final history = fvRows(margin['history']).map(fvMap).toList();
      final date = fvText(margin['as_of'], missing: '缺值');
      final records = history.map((row) {
        final value = fvNumber(row['balance_thousand_twd']);
        return {'date': row['date'],
                'value': value == null ? null : (value / 100000).toStringAsFixed(3)};
      }).where((row) => row['value'] != null).toList();
      final flowItems = fvRows(flows['items']).map(fvMap).toList();
      final latest = history.isEmpty ? <String, dynamic>{} : history.last;
      final changed = fvNumber(latest['change_thousand_twd']);
      final dateLabel = fvText(flows['as_of'], missing: '缺值');
      final previousDate = fvText(flows['previous_as_of'], missing: '缺值');
      return Column(children: [
        fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.trending_up, color: fvTeal),
            const SizedBox(width: 8),
            const Expanded(child: Text('融資餘額 · 近兩週',
                style: TextStyle(color: fvInk, fontSize: 17, fontWeight: FontWeight.w800))),
            fvStatusPill(margin['status'] ?? 'missing'),
          ]),
          const SizedBox(height: 5),
          Text('上市市場盤後資料 · 最近 ${history.length}/10 個交易日 · 截至 $date',
              style: const TextStyle(color: fvMuted, fontSize: 11)),
          if (latest.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text('${_billions(latest['balance_thousand_twd'], divisor: 100000)} 億元',
                style: const TextStyle(color: fvInk, fontSize: 21, fontWeight: FontWeight.w800)),
            Text('較前一交易日 ${changed == null ? '—' : '${changed >= 0 ? '+' : ''}${_billions(changed, divisor: 100000)}'} 億元',
                style: TextStyle(color: changed == null ? fvMuted : fvSignedColor(changed),
                                 fontWeight: FontWeight.w700)),
          ],
          if (records.length >= 2)
            FvVisualSeriesChart(rows: records, label: '融資餘額 · 上市市場',
                unit: '億元', height: 155, showTable: false)
          else fvBoundedState('官方盤後融資餘額資料不足，暫不繪線'),
          if (history.isNotEmpty) ...[
            const Divider(height: 12),
            const Row(children: [
              Expanded(child: Text('交易日', style: TextStyle(color: fvMuted, fontSize: 11))),
              Expanded(child: Text('餘額／億元', textAlign: TextAlign.right,
                  style: TextStyle(color: fvMuted, fontSize: 11))),
              Expanded(child: Text('較前日／億元', textAlign: TextAlign.right,
                  style: TextStyle(color: fvMuted, fontSize: 11))),
            ]),
            for (final row in history.reversed)
              Padding(padding: const EdgeInsets.symmetric(vertical: 3), child: Row(children: [
                Expanded(child: Text(fvText(row['date']).substring(5),
                    style: const TextStyle(fontSize: 12, color: fvInk))),
                Expanded(child: Text(_billions(row['balance_thousand_twd'], divisor: 100000),
                    textAlign: TextAlign.right, style: const TextStyle(fontSize: 12, color: fvInk))),
                Expanded(child: Text(
                    '${(fvNumber(row['change_thousand_twd']) ?? 0) > 0 ? '+' : ''}${_billions(row['change_thousand_twd'], divisor: 100000)}',
                    textAlign: TextAlign.right,
                    style: TextStyle(fontSize: 12,
                      color: fvNumber(row['change_thousand_twd']) == null ? fvMuted :
                          fvSignedColor(fvNumber(row['change_thousand_twd'])!)))),
              ])),
          ],
          const SizedBox(height: 5),
          const Text('單位：億元；每日變化採證交所當日「今日餘額－前日餘額」。資料僅涵蓋上市。',
              style: TextStyle(color: fvMuted, fontSize: 10)),
        ])),
        const SizedBox(height: 10),
        fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.groups_2_outlined, color: fvTeal),
            const SizedBox(width: 8),
            const Expanded(child: Text('法人資金流向 · 買賣超金額',
                style: TextStyle(color: fvInk, fontSize: 17, fontWeight: FontWeight.w800))),
            fvStatusPill(flows['status'] ?? 'missing'),
          ]),
          const SizedBox(height: 5),
          Text('上市市場 · 單位億元 · 資料日 $dateLabel · 比較日 $previousDate',
              style: const TextStyle(color: fvMuted, fontSize: 11)),
          if (fvText(flows['status'], missing: 'missing') == 'missing')
            fvBoundedState('法人官方買賣超金額未取得，不以買賣超股數乘現價代替'),
          for (final row in flowItems)
            Builder(builder: (context) {
              final kind = fvText(row['investor_type']);
              final label = kind == 'foreign' ? '外資' : kind == 'trust' ? '投信' : '自營商';
              final net = fvNumber(row['net_twd']);
              final delta = fvNumber(row['delta_twd']);
              return Padding(padding: const EdgeInsets.symmetric(vertical: 8),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Expanded(child: Text(label, style: const TextStyle(
                        fontWeight: FontWeight.w700, color: fvInk))),
                    Text(net == null ? '—' :
                        '${net > 0 ? '+' : ''}${_billions(net)} 億',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800,
                            color: net == null ? fvMuted : fvSignedColor(net))),
                  ]),
                  Text(delta == null ? '相較比較日：尚無可比資料' :
                      '相較比較日：${delta > 0 ? '+' : ''}${_billions(delta)} 億元',
                      style: TextStyle(color: delta == null ? fvMuted : fvSignedColor(delta),
                                       fontSize: 11)),
                ]));
            }),
          const Text('外資／投信／自營商金額依證交所官方統計；不代表持股增減，也不含上櫃市場。',
              style: TextStyle(color: fvMuted, fontSize: 10)),
        ])),
      ]);
    },
  );

  Widget _personal() => FutureBuilder<dynamic>(
    future: personal,
    builder: (context, snapshot) {
      // No spinner here: market baseline remains visible while this resolves.
      final items = fvRows(fvMap(snapshot.data)['items']);
      if (items.isEmpty) {
        return fvPanel(child: Row(children: [
          const Icon(Icons.bookmark_outline, color: fvTeal),
          const SizedBox(width: 8),
          Expanded(child: Text(
            snapshot.connectionState != ConnectionState.done
                ? '個人追蹤載入中'
                : snapshot.data == null
                    ? '個人追蹤暫時無法取得，可重新整理長期資料'
                    : '目前沒有新的個人追蹤項目',
            key: const Key('today-longterm-personal-empty'),
            style: const TextStyle(fontSize: 13, color: fvMuted),
          )),
        ]));
      }
      return fvPanel(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.auto_awesome_outlined, color: fvTeal, size: 22),
            SizedBox(width: 8),
            Expanded(child: Text('與你最相關的追蹤',
                style: TextStyle(color: fvInk, fontSize: 20, fontWeight: FontWeight.w800))),
          ]),
          const SizedBox(height: 5),
          const Text('來自你自己的關注與待追蹤筆記，不代表投資建議。',
              style: TextStyle(color: fvMuted, fontSize: 11)),
          for (final raw in items.take(3))
            Builder(builder: (context) {
              final row = fvMap(raw);
              final symbol = fvText(row['symbol'], missing: '');
              return ListTile(
                contentPadding: EdgeInsets.zero,
                dense: true,
                leading: Icon(row['kind'] == 'near_owner_target'
                    ? Icons.track_changes_outlined : Icons.flag_outlined, color: fvTeal),
                title: Text(fvText(row['title']),
                    style: const TextStyle(color: fvInk, fontWeight: FontWeight.w700)),
                subtitle: row['data_as_of'] == null ? null :
                    Text('行情日 ${fvText(row['data_as_of'])}'),
                trailing: const Icon(Icons.chevron_right, color: fvMuted),
                onTap: symbol.isEmpty ? null : () => widget.onOpenStock?.call(symbol),
              );
            }),
        ],
      ));
    },
  );

  bool _isEtf(Map<String, dynamic> row) {
    final kind = fvText(row['instrument_kind'], missing: '').toUpperCase();
    return kind == 'ETF' || kind == 'BOND_ETF';
  }

  void _loadSelectedOrderBook(String symbol, {bool refresh = false}) {
    // This only happens on entry, ticker change or explicit button press.
    // Never on the existing 60-second market quote/stock-minute timer.
    if (!widget.active || !foreground || (!refresh && _bookSymbol == symbol)) return;
    _bookSymbol = symbol;
    stockOrderBook = _read(
      '/api/v1/me/portfolio/order-book?symbol=$symbol',
      timeout: const Duration(seconds: 24),
    );
  }

  void _refreshSelectedOrderBook() {
    final symbol = selectedHolding;
    if (symbol == null || !marketActive) return;
    setState(() => _loadSelectedOrderBook(symbol, refresh: true));
  }

  void _selectHolding(String symbol) {
    if (selectedHolding == symbol) return;
    setState(() {
      selectedHolding = symbol;
      stockMinutes = _read('/api/v1/me/portfolio/intraday?symbol=$symbol');
      if (showOrderBook) _loadSelectedOrderBook(symbol);
    });
    _requestHistoricalGapFill(symbol);
  }


  // A single picker replaces the former ticker strip, ETF toggle and second
  // ticker pager. Every position, including ETFs, remains reachable.
  Widget _holdingPicker(List<Map<String, dynamic>> options) {
    final symbols = options.map((row) => fvText(row['symbol'])).toList();
    final index = symbols.indexOf(selectedHolding ?? '');
    final active = index < 0 ? options.first : options[index];
    final currentLabel = '${fvText(active['symbol'])} ${fvText(active['stock_name'], missing: '')}';
    return Row(children: [
      IconButton(
        key: const Key('today-prev-holding'),
        tooltip: '上一檔持股',
        onPressed: index > 0 ? () => _selectHolding(symbols[index - 1]) : null,
        icon: const Icon(Icons.chevron_left, size: 26),
      ),
      Expanded(child: PopupMenuButton<String>(
        key: const Key('today-holding-picker'),
        tooltip: '選擇持股（含 ETF）',
        onSelected: _selectHolding,
        itemBuilder: (context) => [
          for (final row in options)
            PopupMenuItem<String>(
              key: Key('today-live-holding-${fvText(row['symbol'])}'),
              value: fvText(row['symbol']),
              child: Row(children: [
                Expanded(child: Text('${fvText(row['symbol'])} ${fvText(row['stock_name'], missing: '')}',
                    maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 16))),
                if (_isEtf(row)) const Text('ETF', style: TextStyle(fontSize: 13, color: fvMuted)),
                if (selectedHolding == row['symbol'])
                  const Icon(Icons.check, size: 19, color: fvTeal),
              ]),
            ),
        ],
        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Flexible(child: Text(currentLabel, maxLines: 1,
              overflow: TextOverflow.ellipsis,
              key: const Key('today-selected-holding-name'),
              style: const TextStyle(color: fvInk, fontSize: 19,
                  fontWeight: FontWeight.w800))),
          const SizedBox(width: 5),
          const Icon(Icons.arrow_drop_down, color: fvTeal),
        ]),
      )),
      IconButton(
        key: const Key('today-next-holding'),
        tooltip: '下一檔持股',
        onPressed: index >= 0 && index < symbols.length - 1
            ? () => _selectHolding(symbols[index + 1]) : null,
        icon: const Icon(Icons.chevron_right, size: 26),
      ),
    ]);
  }

  Widget _liveHoldings() => FutureBuilder<dynamic>(
    future: ownerQuotes,
    builder: (context, snapshot) {
      final response = fvMap(snapshot.data ?? lastGoodOwnerQuotes);
      final positions = fvRows(response['positions']).map(fvMap)
          .where((row) => row['currency'] == 'TWD' && row['symbol'] != null).toList();
      if (positions.isEmpty && snapshot.connectionState == ConnectionState.done
          && response.isEmpty) {
        return fvBoundedState('持股行情暫時無法讀取；不使用舊報價冒充盤中資料');
      }
      if (positions.isEmpty) return const SizedBox.shrink();
      final ordinary = positions.where((row) => !_isEtf(row)).toList();
      final etfs = positions.where(_isEtf).toList();
      final options = <Map<String, dynamic>>[...ordinary, ...etfs];
      final matches = options.where((row) => row['symbol'] == selectedHolding);
      final selected = matches.isEmpty ? options.first : matches.first;
      final symbol = fvText(selected['symbol']);
      final quoteDate = fvText(selected['price_date'], missing: '');
      final quoteAt = DateTime.tryParse(fvText(selected['quote_at'], missing: ''));
      final localAt = quoteAt?.toUtc().add(const Duration(hours: 8));
      final checkedAt = localAt == null ? '時間缺值'
          : '${localAt.hour.toString().padLeft(2, '0')}:${localAt.minute.toString().padLeft(2, '0')}';
      final isLive = response['market_open'] == true &&
          selected['quote_state'] == 'intraday' &&
          selected['price_status'] == 'available' &&
          quoteAt != null && !DateTime.now().difference(quoteAt).isNegative &&
          DateTime.now().difference(quoteAt).inSeconds <= 120;
      final validChange = selected['price_status'] == 'available' &&
          selected['change'] != null && selected['change_percent'] != null;
      return fvPanel(child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(children: [
            const Expanded(child: Text('持股今日走勢',
                key: Key('today-holding-trend-title'),
                style: TextStyle(color: fvInk, fontSize: 19, fontWeight: FontWeight.w800))),
            if (widget.onOpenStock != null)
              TextButton(
                key: const Key('today-stock-detail-link'),
                onPressed: () => widget.onOpenStock?.call(symbol),
                child: const Text('個股詳情', style: TextStyle(fontSize: 14)),
              ),
          ]),
          _holdingPicker(options),
          Row(children: [
            Expanded(child: fvLimitPriceText(selected,
                legacy.accountingNumber(selected['market_price'], decimals: 2, missing: '—'),
                key: const Key('today-selected-limit-price'), fontSize: 28,
                ordinaryColor: validChange ? fvSignedColor(selected['change']) : fvInk)),
            if (validChange)
              Text('${legacy.accountingNumber(selected['change'], decimals: 2)}  '
                  '${fvSignedPercent(selected['change_percent'])}',
                style: TextStyle(color: fvSignedColor(selected['change']),
                    fontSize: 16, fontWeight: FontWeight.w800)),
          ]),
          const SizedBox(height: 3),
          Row(children: [
            Expanded(child: Text(isLive ? '盤中 $checkedAt'
                : '非即時 · 價格日 ${quoteDate.isEmpty ? '缺值' : quoteDate}',
                key: const Key('today-selected-quote-status'),
                style: const TextStyle(color: fvMuted, fontSize: 13))),
            if (fvPriceLimitState(selected) != FvPriceLimit.none)
              Text(fvPriceLimitState(selected) == FvPriceLimit.up ? '漲停' : '跌停',
                style: TextStyle(
                  color: fvPriceLimitState(selected) == FvPriceLimit.up
                      ? fvLimitUpInk : fvLimitDownInk,
                  fontSize: 13, fontWeight: FontWeight.w800)),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: FilledButton(
              key: const Key('today-stock-tab-chart'),
              onPressed: () => setState(() => showOrderBook = false),
              style: FilledButton.styleFrom(
                  backgroundColor: !showOrderBook ? fvTeal : fvSoft,
                  foregroundColor: !showOrderBook ? Colors.white : fvInk),
              child: const Text('今日走勢', style: TextStyle(fontSize: 15)),
            )),
            const SizedBox(width: 8),
            Expanded(child: FilledButton(
              key: const Key('today-stock-tab-book'),
              onPressed: () => setState(() {
                showOrderBook = true;
                _loadSelectedOrderBook(symbol);
              }),
              style: FilledButton.styleFrom(
                  backgroundColor: showOrderBook ? fvTeal : fvSoft,
                  foregroundColor: showOrderBook ? Colors.white : fvInk),
              child: const Text('買賣五檔', style: TextStyle(fontSize: 15)),
            )),
          ]),
          const SizedBox(height: 8),
          if (!showOrderBook) ...[
            FutureBuilder<dynamic>(
              key: ValueKey('today-intraday-$symbol'),
              future: stockMinutes,
              builder: (context, state) {
                final data = fvMap(state.data);
                final points = fvRows(data['items']);
                final referenceDate = fvText(data['previous_close_date'], missing: '');
                final asOfDate = fvText(data['as_of'], missing: '');
                final previousClose = data['previous_close_source'] == 'official_previous_close' &&
                        referenceDate.isNotEmpty && asOfDate.isNotEmpty &&
                        referenceDate.compareTo(asOfDate) < 0
                    ? fvNumber(data['previous_close']) : null;
                return FvIntradayProgressChart(rows: points,
                    label: '$symbol · 今日分鐘走勢',
                    unit: '元／股', height: 205,
                    previousClose: previousClose);
              },
            ),
            _backfillCaption(symbol),
          ] else
            StockOrderBookPanel(
              key: ValueKey('today-order-book-$symbol'),
              symbol: symbol, snapshot: stockOrderBook,
              onRefresh: _refreshSelectedOrderBook,
            ),
        ],
      ));
    },
  );

  // An exchange MIS tick may contain its own prior close; otherwise use
  // a strictly earlier, published Core TAIEX close with real lineage.
  double? _taiexSummaryPreviousClose(Map<String, dynamic> section) {
    final data = fvMap(section['data']);
    final date = fvText(section['as_of'], missing: '');
    final at = DateTime.tryParse(fvText(data['quote_at'], missing: ''));
    final state = fvText(data['quote_state'], missing: '');
    final quoteDay = at?.toUtc().add(const Duration(hours: 8))
        .toIso8601String().substring(0, 10);
    final exchangeReference = fvNumber(data['quote_previous_close']);
    if (date.isNotEmpty && quoteDay == date &&
        {'intraday', 'closing_pending_eod', 'stale'}.contains(state) &&
        exchangeReference != null && exchangeReference.isFinite &&
        exchangeReference > 0) {
      return exchangeReference;
    }
    final tradeDate = DateTime.tryParse(date);
    if (tradeDate == null) return null;
    final candidates = fvRows(data['history_points']).map(fvMap).where((row) {
      final observedDate = DateTime.tryParse(fvText(row['date'], missing: ''));
      final close = fvNumber(row['value']);
      return observedDate != null && observedDate.isBefore(tradeDate) &&
          tradeDate.difference(observedDate).inDays <= 7 &&
          close != null && close.isFinite && close > 0 &&
          fvText(row['source_id'], missing: '').isNotEmpty &&
          fvText(row['provenance_id'], missing: '').isNotEmpty;
    }).toList()
      ..sort((a, b) => fvText(b['date']).compareTo(fvText(a['date'])));
    return candidates.isEmpty ? null : fvNumber(candidates.first['value']);
  }

  String _taiexQuoteLabel(Map<String, dynamic> section) {
    final data = fvMap(section['data']);
    final at = DateTime.tryParse(fvText(data['quote_at'], missing: ''));
    final state = fvText(data['quote_state'], missing: '');
    final date = fvText(section['as_of'], missing: '');
    final now = DateTime.now();
    final today = now.toUtc().add(const Duration(hours: 8));
    final tick = at?.toUtc().add(const Duration(hours: 8));
    final sameDay = tick != null && tick.year == today.year &&
        tick.month == today.month && tick.day == today.day;
    final age = at == null ? null : now.difference(at).inSeconds;
    if (marketHours && state == 'intraday' && sameDay &&
        age != null && age >= 0 && age <= 120) {
      return '盤中 ${tick.hour.toString().padLeft(2, '0')}:${tick.minute.toString().padLeft(2, '0')}';
    }
    if (state.isNotEmpty) return '非即時 · ${date.isEmpty ? '日期缺值' : date}';
    return date.isNotEmpty ? '資料日 $date' : '行情日期缺值';
  }

  // A single compact index card keeps today's point and percent change
  // visible without opening the chart. The chart remains on-demand.
  Widget _compactMarket() => FutureBuilder<dynamic>(
    future: market,
    builder: (context, snapshot) {
      final root = fvMap(snapshot.data ?? lastGoodMarket);
      final section = fvMap(fvMap(root['sections'])['taiex']);
      if (section.isEmpty) {
        return Column(children: [
          fvPanel(padding: const EdgeInsets.symmetric(
              horizontal: 14, vertical: 10),
            child: const Row(children: [
              Text('加權指數', style: TextStyle(color: fvInk,
                  fontSize: 15, fontWeight: FontWeight.w800)),
              Spacer(),
              Text('行情尚未取得', style: TextStyle(color: fvMuted, fontSize: 14)),
            ])),
          fvBoundedState(snapshot.connectionState == ConnectionState.done
              ? '大盤行情暫時無法取得' : '大盤資料仍在讀取；其他資訊可先使用'),
        ]);
      }
      final data = fvMap(section['data']);
      final current = fvNumber(data['close'] ?? data['index'] ?? data['value']);
      final previous = _taiexSummaryPreviousClose(section);
      final comparable = current != null && current.isFinite && current > 0 &&
          previous != null && previous.isFinite && previous > 0;
      final change = comparable ? current - previous : null;
      final ratio = comparable && change != null ? change / previous : null;
      final changeColor = change == null ? fvMuted : fvSignedColor(change);
      final points = change == null ? '—' :
          '${change > 0 ? '+' : change < 0 ? '-' : ''}${legacy.accountingNumber(change.abs(), decimals: 2)} 點';
      final percent = ratio == null ? '—' : fvSignedPercent(ratio);
      return fvPanel(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        child: InkWell(
          key: const Key('today-market-summary'),
          onTap: () => showModalBottomSheet<void>(
            context: context, isScrollControlled: true,
            builder: (sheetContext) => SafeArea(
              child: SizedBox(
                height: MediaQuery.sizeOf(sheetContext).height * 0.7,
                child: ListView(padding: const EdgeInsets.all(16), children: [
                  const Text('加權指數 · 今日分鐘走勢',
                      style: TextStyle(color: fvInk, fontSize: 20,
                          fontWeight: FontWeight.w800)),
                  const SizedBox(height: 10),
                  _market(),
                ]),
              ),
            ),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(children: [
                const Text('加權指數', style: TextStyle(color: fvInk,
                    fontSize: 15, fontWeight: FontWeight.w800)),
                const SizedBox(width: 10),
                Expanded(child: Align(alignment: Alignment.centerRight,
                  child: FittedBox(fit: BoxFit.scaleDown,
                    alignment: Alignment.centerRight,
                    child: Text(_value(section),
                      key: const Key('today-market-index-value'),
                      maxLines: 1, softWrap: false,
                      style: const TextStyle(color: fvInk, fontSize: 24,
                          fontWeight: FontWeight.w900)),
                  ),
                )),
                const SizedBox(width: 6),
                const Icon(Icons.chevron_right, color: fvTeal),
              ]),
              const SizedBox(height: 3),
              Row(children: [
                Expanded(child: Text(_taiexQuoteLabel(section),
                    key: const Key('today-market-quote-status'),
                    maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: fvMuted, fontSize: 12))),
                const SizedBox(width: 6),
                if (comparable)
                  Flexible(flex: 3, child: Align(
                    alignment: Alignment.centerRight,
                    child: FittedBox(fit: BoxFit.scaleDown,
                      alignment: Alignment.centerRight,
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        Text(points,
                          key: const Key('today-market-change-points'),
                          maxLines: 1, softWrap: false,
                          style: TextStyle(color: changeColor, fontSize: 17,
                              fontWeight: FontWeight.w800)),
                        const SizedBox(width: 8),
                        Text(percent,
                          key: const Key('today-market-change-percent'),
                          maxLines: 1, softWrap: false,
                          style: TextStyle(color: changeColor, fontSize: 17,
                              fontWeight: FontWeight.w800)),
                      ]),
                    ),
                  ))
                else
                  const Text('漲跌待可比前收',
                    key: Key('today-market-change-unavailable'),
                    style: TextStyle(color: fvMuted, fontSize: 13)),
              ]),
            ],
          ),
        ),
      );
    },
  );

  Widget _market() => FutureBuilder<dynamic>(
    future: market,
    builder: (context, snapshot) {
      final root = fvMap(snapshot.data ?? lastGoodMarket);
      final sections = fvMap(root['sections']);
      return Column(children: [
        fvSectionTitle(context, marketHours ? '盤中即時' : '行情與最近觀測',
            trailing: marketHours ? '頁面可見時約每60秒更新' : '休市不自動輪詢'),
        IntrinsicHeight(
          child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            _benchmark('加權指數', Icons.show_chart, sections['taiex']),
          ]),
        ),
        const SizedBox(height: 10),
        if (sections.isNotEmpty)
          _taiexTrend(sections['taiex']),
        _backfillCaption('TAIEX'),
        if (snapshot.connectionState != ConnectionState.done && sections.isEmpty)
          fvBoundedState('大盤資料仍在讀取；其他資訊可先使用')
        else if (snapshot.connectionState == ConnectionState.done && snapshot.data == null)
          fvPanel(child: Row(children: [
            Expanded(child: Text(lastGoodMarket == null ? '市場基礎資料暫時無法使用' : '更新失敗，保留上次資料與日期')),
            TextButton(
              onPressed: () => setState(() { market = _readCoreMarket(); }),
              child: const Text('重試'),
            ),
          ])),
      ]);
    },
  );

  Widget _longTermFlowSnapshot() => FutureBuilder<dynamic>(
    future: marketFlows,
    builder: (context, snapshot) {
      final result = fvMap(snapshot.data);
      final margin = fvMap(result['margin']);
      final flow = fvMap(result['institutional']);
      final history = fvRows(margin['history']).map(fvMap).toList();
      final latest = history.isEmpty ? null : history.last;
      final balance = latest == null
          ? null : fvNumber(latest['balance_thousand_twd']);
      final flowDate = fvText(flow['as_of'], missing: '缺值');
      final marginDate = fvText(margin['as_of'], missing: '缺值');
      return fvPanel(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('盤後資金快覽',
              style: TextStyle(color: fvInk, fontSize: 14,
                  fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(balance == null
              ? '融資餘額：${snapshot.connectionState == ConnectionState.done ? '暫無資料' : '載入中'}'
              : '融資餘額 ${_billions(balance, divisor: 100000)} 億元 · $marginDate',
              style: const TextStyle(color: fvInk, fontSize: 12)),
          Text('三大法人買賣超資料日：$flowDate · 詳細金額見下方',
              style: const TextStyle(color: fvMuted, fontSize: 11)),
        ]),
      );
    },
  );

  Widget _historicalMarket() => FutureBuilder<dynamic>(
    future: market,
    builder: (context, snapshot) {
      final root = fvMap(snapshot.data ?? lastGoodMarket);
      final sections = fvMap(root['sections']);
      final section = fvMap(sections['taiex']);
      final data = fvMap(section['data']);
      // The long-horizon headline is based on two real dated EOD records,
      // never on an intraday sample or a provisional current quote.
      final closes = fvRows(data['history_points']).map(fvMap)
          .where((row) {
            final date = DateTime.tryParse(fvText(row['date'], missing: ''));
            final value = fvNumber(row['value']);
            return date != null && value != null &&
                value.isFinite && value > 0;
          }).toList()
        ..sort((a, b) => fvText(a['date']).compareTo(fvText(b['date'])));
      final latest = closes.isEmpty ? null : closes.last;
      final prior = closes.length < 2 ? null : closes[closes.length - 2];
      final latestValue = latest == null ? null : fvNumber(latest['value']);
      final priorValue = prior == null ? null : fvNumber(prior['value']);
      final difference = latestValue == null || priorValue == null
          ? null : latestValue - priorValue;
      final changeRatio = difference == null || priorValue == null ||
          priorValue <= 0 ? null : difference / priorValue;
      final sourceIds = fvRows(data['history_source_ids']);
      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Expanded(child: Text('市場長期趨勢',
              style: TextStyle(color: fvInk, fontSize: 17,
                  fontWeight: FontWeight.w800))),
          TextButton.icon(
            key: const Key('today-longterm-refresh'),
            onPressed: () => setState(() {
              market = _loadMarketWithoutPerf();
              _loadResearch(refresh: true);
            }),
            icon: const Icon(Icons.refresh, size: 17),
            label: const Text('更新資料'),
          ),
        ]),
        if (latest != null)
          fvPanel(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('加權指數 · 最新正式收盤',
                  style: TextStyle(color: fvMuted, fontSize: 13)),
              const SizedBox(height: 3),
              Row(children: [
                Expanded(child: FittedBox(
                  fit: BoxFit.scaleDown, alignment: Alignment.centerLeft,
                  child: Text('${legacy.accountingNumber(latestValue, decimals: 2)} 點',
                      key: const Key('today-longterm-close'),
                      maxLines: 1, softWrap: false,
                      style: const TextStyle(color: fvInk,
                          fontSize: 25, fontWeight: FontWeight.w900)),
                )),
                if (difference != null && changeRatio != null)
                  Text(
                    '${difference > 0 ? '+' : difference < 0 ? '-' : ''}'
                    '${legacy.accountingNumber(difference.abs(), decimals: 2)} 點'
                    '（${fvSignedPercent(changeRatio)}）',
                    key: const Key('today-longterm-change'),
                    style: TextStyle(color: fvSignedColor(difference),
                        fontSize: 13, fontWeight: FontWeight.w800),
                  ),
              ]),
              const SizedBox(height: 4),
              Text('收盤日 ${fvText(latest['date'])}'
                  ' · ${prior == null ? '缺少前期可比收盤' : '比較日 ${fvText(prior['date'])}'}'
                  ' · 來源 ${sourceIds.isEmpty ? '待查' : sourceIds.join('、')}',
                  key: const Key('today-longterm-asof'),
                  style: const TextStyle(color: fvMuted, fontSize: 11)),
            ]),
          )
        else
          fvBoundedState('尚無兩期可比較的正式收盤資料；不使用盤中價格替代'),
        const SizedBox(height: 8),
        _longTermFlowSnapshot(),
        const SizedBox(height: 8),
        if (sections['taiex'] != null)
          _taiexTrend(sections['taiex'], intradayOnly: false)
        else
          fvBoundedState('歷史收盤行情尚未就緒'),
      ]);
    },
  );

  Widget _brief() => FutureBuilder<dynamic>(
    future: brief,
    builder: (context, snapshot) {
      final reports = fvRows(fvMap(snapshot.data));
      final report = reports.isEmpty ? <String, dynamic>{} : fvMap(reports.first);
      final nested = fvMap(report['data']);
      final data = nested.isEmpty ? report : nested;
      final highlights = fvRows(data['highlights']);
      final sectors = fvRows(data['sector_rotation']);
      final topics = fvRows(data['topics'] ?? data['hot_topics']);
      final candidates = fvRows(data['candidates']);
      final loading = snapshot.connectionState != ConnectionState.done;
      final unavailable = !loading && (snapshot.data == null || reports.isEmpty);

      if ((report['model_validation_status'] ?? data['model_validation_status']) != 'validated') {
        return fvPanel(child: ExpansionTile(
          key: const PageStorageKey<String>('today-research-state'),
          title: const Text('研究狀態'),
          subtitle: Text(loading ? '研究內容載入中' : unavailable ? '研究內容尚未就緒' : '模型驗證尚未完成'),
          children: [
            const Text('完成模型驗證後才啟用整合報告'),
            TextButton(
              onPressed: () => setState(() { brief = _read('/api/v1/public/daily-brief'); }),
              child: const Text('重試'),
            ),
          ],
        ));
      }

      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        fvSectionTitle(context, '市場判讀',
            trailing: loading ? '載入中' : fvText(report['analysis_as_of'], missing: '尚未就緒')),
        if (loading)
          fvBoundedState('研究內容載入中；市場基礎資料可先使用')
        else if (unavailable)
          fvPanel(child: Row(children: [
            const Expanded(child: Text('研究內容尚未就緒')),
            TextButton(
              onPressed: () => setState(() { brief = _read('/api/v1/public/daily-brief'); }),
              child: const Text('重試'),
            ),
          ]))
        else
          fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Icon(Icons.radar_outlined, color: fvTeal),
              const SizedBox(width: 8),
              Expanded(child: Text(legacy.uiLabel(data['market_regime'] ?? data['market_status'] ?? 'available'),
                  style: const TextStyle(color: fvInk, fontSize: 17, fontWeight: FontWeight.w800))),
            ]),
            if (data['summary'] != null) ...[
              const SizedBox(height: 8),
              Text('${data['summary']}', style: const TextStyle(color: fvInk, height: 1.45)),
            ],
          ])),
        fvSectionTitle(context, '今日三件事'),
        if (highlights.isEmpty)
          fvBoundedState(loading ? '研究重點載入中' : '目前沒有可發布重點')
        else
          fvPanel(child: Column(children: [
            for (var i = 0; i < highlights.take(3).length; i++)
              Padding(
                padding: EdgeInsets.only(bottom: i == highlights.take(3).length - 1 ? 0 : 10),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  CircleAvatar(radius: 12, backgroundColor: fvSoft,
                      child: Text('${i + 1}', style: const TextStyle(color: fvTeal, fontSize: 11, fontWeight: FontWeight.w800))),
                  const SizedBox(width: 9),
                  Expanded(child: Text(fvText(highlights[i] is Map
                      ? (fvMap(highlights[i])['title'] ?? fvMap(highlights[i])['summary'])
                      : highlights[i], missing: '重點'),
                      style: const TextStyle(color: fvInk, height: 1.4))),
                ]),
              ),
          ])),
        fvSectionTitle(context, '產業輪動／熱門話題'),
        if (sectors.isEmpty && topics.isEmpty)
          fvBoundedState(loading ? '產業與話題載入中' : '目前沒有可發布內容')
        else
          fvPanel(child: Column(children: [
            for (final item in sectors.take(3))
              ListTile(contentPadding: EdgeInsets.zero, dense: true,
                leading: const Icon(Icons.trending_up, color: fvTeal),
                title: Text(fvText(item is Map
                    ? (fvMap(item)['industry'] ?? fvMap(item)['name'] ?? fvMap(item)['title'])
                    : item))),
            for (final item in topics.take(3))
              ListTile(contentPadding: EdgeInsets.zero, dense: true,
                leading: const Icon(Icons.tag_outlined, color: fvTeal),
                title: Text(fvText(item is Map
                    ? (fvMap(item)['title'] ?? fvMap(item)['topic'] ?? fvMap(item)['summary'])
                    : item))),
          ])),
        fvSectionTitle(context, '候選股健康'),
        if (candidates.isEmpty)
          fvBoundedState(loading ? '候選股資料載入中' : '目前沒有可發布候選股')
        else
          ...candidates.take(5).map((item) {
            final row = fvMap(item);
            final symbol = fvText(row['stock_id'] ?? row['symbol']);
            return fvPanel(padding: EdgeInsets.zero, child: ListTile(
              onTap: symbol == '—' ? null : () => widget.onOpenStock?.call(symbol),
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
              title: Text(fvText(row['stock_name'] ?? row['name'], missing: symbol),
                  style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
              subtitle: Text('$symbol · ${fvText(row['analysis_as_of'] ?? report['analysis_as_of'], missing: '資料日未定')}'),
              trailing: Text(row['mart_health_score'] == null
                  ? legacy.uiLabel(row['data_status'] ?? 'partial')
                  : '健康度 ${legacy.accountingNumber(row['mart_health_score'])}',
                  style: const TextStyle(color: fvTeal, fontWeight: FontWeight.w700)),
            ));
          }),
        fvSectionTitle(context, '全市場篩選'),
        fvBoundedState(data['screening'] == null && data['market_screening'] == null
            ? '全市場篩選結果尚未就緒'
            : fvText(data['screening'] ?? data['market_screening'])),
      ]);
    },
  );

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: fvCanvas,
    child: SafeArea(
      bottom: false,
      child: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(14, 8, 14, 4),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            fvPageTitle(context, '今日'),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(child: FilledButton(
                key: const Key('today-tab-live'),
                onPressed: () => _switchTodayTab(0),
                style: FilledButton.styleFrom(
                    backgroundColor: todayTab == 0 ? fvTeal : fvSoft,
                    foregroundColor: todayTab == 0 ? Colors.white : fvInk),
                child: const Text('盤中變化'),
              )),
              const SizedBox(width: 9),
              Expanded(child: FilledButton(
                key: const Key('today-tab-longterm'),
                onPressed: () => _switchTodayTab(1),
                style: FilledButton.styleFrom(
                    backgroundColor: todayTab == 1 ? fvTeal : fvSoft,
                    foregroundColor: todayTab == 1 ? Colors.white : fvInk),
                child: const Text('長期觀察'),
              )),
            ]),
          ]),
        ),
        Expanded(child: ListView(
          key: PageStorageKey('today-tab-scroll-$todayTab'),
          padding: const EdgeInsets.fromLTRB(14, 4, 14, 28),
          children: [
            if (todayTab == 0) ...[
              _compactMarket(),
              _liveHoldings(),
            ] else ...[
              _historicalMarket(),
              _leverageFlow(),
              _personal(),
              _brief(),
            ],
            const Padding(
              padding: EdgeInsets.only(top: 12),
              child: Text('本服務提供研究資訊，不構成投資建議。',
                  style: TextStyle(color: fvMuted, fontSize: 12)),
            ),
          ],
        )),
      ]),
    ),
  );
}
