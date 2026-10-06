import 'dart:async';

import 'package:flutter/material.dart';

import 'final_charts.dart';
import 'final_perf.dart';
import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalLedgerPage extends StatefulWidget {
  const FinalLedgerPage(
    this.api, {
    this.onOpenStock,
    this.active = true,
    this.now = DateTime.now,
    super.key,
  });

  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;
  final bool active;
  final DateTime Function() now;

  @override
  State<FinalLedgerPage> createState() => _FinalLedgerPageState();
}

class _FinalLedgerPageState extends State<FinalLedgerPage>
    with WidgetsBindingObserver {
  int section = 0;
  int recordGrouping = 0;
  int yearFilter = DateTime.now().year;
  final Map<String, Future<dynamic>> requestCache = {};
  late Future<List<dynamic>> coreData = loadCore();
  Future<List<dynamic>>? sectionData;
  Timer? quoteTimer;
  bool quoteBusy = false;
  bool pnlRecalcBusy = false;
  bool foreground = true;
  int quoteGeneration = 0;
  DateTime? offSessionQuoteDate;
  DateTime? post1430QuoteDate;
  Map<String, dynamic>? intraday;
  String? quoteError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    foreground = WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) startQuotes();
    });
  }

  bool get quotesActive =>
      widget.active &&
      section == 0 &&
      foreground &&
      (ModalRoute.of(context)?.isCurrent ?? true);

  DateTime get taipeiNow =>
      widget.now().toUtc().add(const Duration(hours: 8));

  bool _sameTaipeiDay(DateTime? left, DateTime right) =>
      left != null &&
      left.year == right.year &&
      left.month == right.month &&
      left.day == right.day;

  bool _marketHoursAt(DateTime taipei) {
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 540 && minutes < 810;
  }

  bool get marketHours => _marketHoursAt(taipeiNow);

  bool _after1430(DateTime taipei) {
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 870;
  }

  bool _closingPending(DateTime taipei) {
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 810 && minutes < 870;
  }

  void startQuotes() {
    quoteTimer?.cancel();
    if (!quotesActive) return;
    final now = taipeiNow;
    if (_marketHoursAt(now)) {
      quoteTimer = Timer.periodic(const Duration(minutes: 1), (_) {
        if (!marketHours) {
          quoteTimer?.cancel();
          startQuotes();
        } else if (quotesActive) {
          unawaited(refreshQuotes());
        }
      });
      unawaited(refreshQuotes());
      return;
    }
    if (_after1430(now)) {
      if (!_sameTaipeiDay(post1430QuoteDate, now)) {
        unawaited(refreshQuotes());
      }
      return;
    }
    if (!_sameTaipeiDay(offSessionQuoteDate, now)) {
      unawaited(refreshQuotes());
    }
    if (_closingPending(now)) {
      final handoff = DateTime(now.year, now.month, now.day, 14, 30);
      final delay = handoff.difference(now);
      if (!delay.isNegative) {
        quoteTimer = Timer(delay, () {
          if (quotesActive) unawaited(refreshQuotes());
        });
      }
    }
  }

  Future<void> refreshQuotes({bool force = false}) async {
    if (!quotesActive || quoteBusy) return;
    final generation = quoteGeneration;
    setState(() => quoteBusy = true);
    try {
      final result = await (force
              ? widget.api.post('/api/v1/me/portfolio/quotes/refresh', const {})
              : widget.api.get('/api/v1/me/portfolio/quotes'))
          .timeout(const Duration(seconds: 60));
      if (mounted && generation == quoteGeneration && quotesActive) {
        final local = taipeiNow;
        setState(() {
          intraday = Map<String, dynamic>.from(result as Map);
          quoteError = null;
          if (!_marketHoursAt(local)) {
            offSessionQuoteDate = local;
            if (_after1430(local)) post1430QuoteDate = local;
          }
        });
        if (intraday!['market_open'] == false && !_closingPending(local)) {
          quoteTimer?.cancel();
        }
      }
    } catch (_) {
      if (mounted && generation == quoteGeneration && quotesActive) {
        setState(() => quoteError = '報價暫時無法更新，保留最後資料；請查看報價時間');
      }
    } finally {
      if (mounted && generation == quoteGeneration) {
        setState(() => quoteBusy = false);
      }
    }
  }

  @override
  void didUpdateWidget(FinalLedgerPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active != widget.active) {
      quoteGeneration++;
      quoteBusy = false;
      quoteTimer?.cancel();
      if (widget.active && section == 0) startQuotes();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (!foreground) {
      quoteTimer?.cancel();
      quoteGeneration++;
      quoteBusy = false;
    } else if (section == 0) {
      startQuotes();
    }
  }

  @override
  void dispose() {
    quoteGeneration++;
    quoteTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<dynamic> safe(String path) async {
    try {
      return await widget.api.get(path);
    } catch (_) {
      return null;
    }
  }

  Future<dynamic> cached(String path) =>
      requestCache.putIfAbsent(path, () => safe(path));

  Future<List<dynamic>> loadCore() async {
    final stopwatch = Stopwatch()..start();
    final currentYear = DateTime.now().year;
    try {
      return await Future.wait([
        cached('/api/v1/me/portfolio/summary'),
        cached('/api/v1/me/journal/pnl?year=$currentYear'),
        cached('/api/v1/me/journal/positions'),
        cached('/api/v1/me/journal/history?year=$currentYear'),
      ]);
    } finally {
      stopwatch.stop();
      FinalPerf.recordCore('ledger', stopwatch.elapsed);
    }
  }

  Future<List<dynamic>> loadSection(int target, int year) {
    return switch (target) {
      1 => Future.wait([
          cached('/api/v1/me/journal/history?year=$year'),
          cached('/api/v1/me/journal/monthly-summary?year=$year'),
          cached('/api/v1/me/journal/symbol-summary?year=$year'),
          cached('/api/v1/me/journal/pnl?year=$year'),
        ]),
      2 => Future.wait([
          cached('/api/v1/me/journal/pnl?year=$year'),
          cached('/api/v1/me/portfolio/performance?year=$year'),
          cached('/api/v1/me/journal/monthly-summary?year=$year'),
          cached('/api/v1/me/journal/history?year=$year'),
        ]),
      3 => Future.wait([cached('/api/v1/me/notes')]),
      _ => Future.value(const <dynamic>[]),
    };
  }

  void reload() {
    quoteGeneration++;
    quoteTimer?.cancel();
    setState(() {
      requestCache.clear();
      coreData = loadCore();
      sectionData = section == 0 ? null : loadSection(section, yearFilter);
      intraday = null;
      quoteError = null;
      quoteBusy = false;
      offSessionQuoteDate = null;
      post1430QuoteDate = null;
    });
    if (section == 0) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) startQuotes();
      });
    }
  }

  void selectYear(int year) {
    if (year == yearFilter) return;
    setState(() {
      yearFilter = year;
      if (section == 1 || section == 2) {
        sectionData = loadSection(section, year);
      }
    });
  }

  Widget yearSelector() {
    final currentYear = DateTime.now().year;
    return MenuAnchor(
      builder: (context, controller, child) => OutlinedButton.icon(
        key: const Key('ledger-year-selector'),
        onPressed: () =>
            controller.isOpen ? controller.close() : controller.open(),
        icon: const Icon(Icons.calendar_month, size: 18),
        label: Text('年度：$yearFilter'),
      ),
      menuChildren: [
        for (var year = currentYear; year >= currentYear - 5; year--)
          MenuItemButton(
            onPressed: () => selectYear(year),
            child: Text('$year 年'),
          ),
      ],
    );
  }

  Future<void> addTrade() async {
    final payload = await legacy.transactionDialog(context);
    if (payload == null) return;
    try {
      await widget.api.post('/api/v1/me/journal/events', payload);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text(legacy.portfolioPendingMessage)),
      );
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('交易尚未儲存')),
        );
      }
    }
  }

  Future<void> correctTrade(Map<String, dynamic> row) async {
    final replacement = await legacy.transactionDialog(
      context,
      initial: row,
      title: '建立更正',
    );
    if (replacement == null || !mounted) return;
    try {
      await widget.api.post(
        '/api/v1/me/journal/events/${row['event_id']}/corrections',
        {
          'expected_version': row['record_version'],
          'replacement': replacement,
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text(legacy.portfolioPendingMessage)),
      );
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('交易更正尚未儲存')),
        );
      }
    }
  }

  Future<void> recalculatePnl() async {
    if (pnlRecalcBusy) return;
    setState(() => pnlRecalcBusy = true);
    try {
      await widget.api.post('/api/v1/me/journal/recalculate', const {});
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('損益已重新計算')),
      );
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('損益重新計算失敗，請稍後重試')),
        );
      }
    } finally {
      if (mounted) setState(() => pnlRecalcBusy = false);
    }
  }

  Future<void> addNote() async {
    final body = await legacy.textDialog(context, '新增筆記', '筆記內容');
    if (body == null || body.trim().isEmpty) return;
    try {
      await widget.api.post('/api/v1/me/notes', {'body': body.trim()});
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('筆記尚未儲存')),
        );
      }
    }
  }

  Widget metricGrid({
    required String marketValue,
    required String unrealized,
    required String unrealizedReturn,
    required String ytd,
    required Object? unrealizedAmount,
    required Object? unrealizedReturnAmount,
    required Object? ytdAmount,
    required Map<String, dynamic> aggregate,
    required bool withheld,
  }) => Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: fvMetricTile(
                  '持股市值',
                  marketValue,
                  detail: '估值日 ${fvText(aggregate['valuation_date'])}',
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: fvMetricTile(
                  '未實現損益',
                  unrealized,
                  detail: '報酬 $unrealizedReturn',
                  valueColor: withheld ? null : fvSignedColor(unrealizedAmount),
                  detailColor:
                      withheld ? null : fvSignedColor(unrealizedReturnAmount),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: fvMetricTile(
                  '本年已實現損益',
                  ytd,
                  detail: ytd == '待更新／尚未確認'
                      ? 'Private Mart 尚未確認時不補 0'
                      : ytd == '資料不足'
                          ? '年度損益目前無法確認'
                          : ytd == '0'
                              ? '本年度確認無交易'
                              : '正式年度損益',
                  valueColor: fvSignedColor(ytdAmount),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: fvMetricTile(
                  '估值狀態',
                  withheld
                      ? '暫不發布'
                      : legacy.uiLabel(
                          aggregate['valuation_status'] ??
                              (aggregate.isEmpty ? 'partial' : 'available'),
                        ),
                  detail:
                      'ledger v${fvText(aggregate['ledger_version'], missing: '—')}',
                ),
              ),
            ],
          ),
        ],
      );

  Widget holdings(List<dynamic> positions) {
    if (positions.isEmpty) return fvBoundedState('目前無持股或持股資料尚未取得');
    return Column(
      children: [
        for (final item in positions)
          Builder(builder: (context) {
            final row = fvMap(item);
            final symbol = fvText(row['symbol']);
            final reason = legacy.portfolioMissingReasonLabel(row['missing_reason']);
            return fvPanel(
              padding: EdgeInsets.zero,
              child: InkWell(
                borderRadius: BorderRadius.circular(20),
                onTap: () => widget.onOpenStock?.call(symbol),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  legacy.stockDisplayName(row),
                                  style: const TextStyle(
                                    color: fvInk,
                                    fontSize: 17,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  '持有 ${legacy.accountingNumber(row['shares'])} 股',
                                  style: const TextStyle(color: fvInk),
                                ),
                                Text(
                                  '現價 ${legacy.accountingNumber(row['market_price'], decimals: 2, missing: '缺價')} · 均價 ${legacy.accountingNumber(row['average_cost'], decimals: 2)}',
                                  style: const TextStyle(
                                    color: fvMuted,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 10),
                          ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 118),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  '未實現 ${legacy.accountingNumber(row['unrealized_pnl'], missing: '資料不足')}',
                                  key: Key('holding-pnl-$symbol'),
                                  textAlign: TextAlign.end,
                                  style: TextStyle(
                                    color: fvSignedColor(row['unrealized_pnl']),
                                    fontSize: 16,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                Text(
                                  legacy.portfolioReturnLabel(
                                    row['unrealized_return'],
                                  ),
                                  key: Key('holding-return-$symbol'),
                                  style: TextStyle(
                                    color: fvSignedColor(row['unrealized_return']),
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        row['price_source'] == 'twse_mis'
                            ? 'MIS 最新成交 · 報價 ${fvText(row['quote_at'])} · ${fvText(row['quote_state'])}'
                            : '正式行情 · 行情日 ${fvText(row['price_date'])} · ${row['price_status'] == null ? '狀態未知' : legacy.uiLabel(row['price_status'])}',
                        style: const TextStyle(color: fvMuted, fontSize: 11),
                      ),
                      if (reason.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          reason,
                          style: const TextStyle(color: fvMuted, fontSize: 11),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            );
          }),
      ],
    );
  }

  String realizedPnlLabel(Map<String, dynamic>? row) {
    if (row == null) return '已實現損益 待更新';
    final currency = fvText(row['currency'], missing: 'TWD');
    return '已實現損益 $currency ${legacy.accountingNumber(row['realized_pnl'], missing: '資料不足')}';
  }

  String annualRealizedPnlLabel(dynamic raw, List<dynamic> history) {
    if (raw == null) return '年度已實現損益 資料不足';
    final rows = fvRows(raw);
    if (rows.isEmpty) {
      return history.isEmpty ? '年度已實現損益 0' : '年度已實現損益 待更新';
    }
    if (rows.length > 1) return '年度已實現損益 多幣別';
    return '年度${realizedPnlLabel(fvMap(rows.first))}';
  }

  Widget recordTile(Map<String, dynamic> row) {
    final quantity = row['shares'] != null && row['price'] != null
        ? ' · ${legacy.accountingNumber(row['shares'])} 股 × ${legacy.accountingNumber(row['price'], decimals: 2)}'
        : '';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      dense: true,
      title: Text(
        '${legacy.uiLabel(row['event_type'])} · ${legacy.stockDisplayName(row)}',
      ),
      subtitle: Text('${fvText(row['trade_date'])}$quantity'),
      trailing: row['event_id'] != null && row['record_version'] != null
          ? IconButton(
              tooltip: '建立更正',
              icon: const Icon(Icons.edit_note),
              onPressed: () => correctTrade(row),
            )
          : null,
    );
  }

  Widget recordGroup({
    required Key key,
    required String title,
    required String realized,
    required Object? realizedAmount,
    required List<Map<String, dynamic>> events,
  }) =>
      fvPanel(
        padding: EdgeInsets.zero,
        child: ExpansionTile(
          key: key,
          initiallyExpanded: false,
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          title: Text(
            title,
            style: const TextStyle(
              color: fvInk,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          subtitle: Text(
            realized,
            style: TextStyle(
              color: realizedAmount == null
                  ? fvMuted
                  : fvSignedColor(realizedAmount),
              fontWeight: FontWeight.w700,
            ),
          ),
          children: [
            if (events.isEmpty)
              const Padding(
                padding: EdgeInsets.only(bottom: 10),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    '目前沒有可顯示的交易明細',
                    style: TextStyle(color: fvMuted, fontSize: 12),
                  ),
                ),
              )
            else
              for (final row in events) recordTile(row),
          ],
        ),
      );

  Widget records(
    List<dynamic> history,
    List<dynamic> monthly,
    List<dynamic> symbolSummary,
  ) {
    final effective = legacy.effectiveLedgerEvents(history);
    if (effective.isEmpty && monthly.isEmpty && symbolSummary.isEmpty) {
      return fvBoundedState('本年度尚無交易紀錄');
    }
    final summaries = <int, Map<String, dynamic>>{};
    for (final item in monthly) {
      final row = fvMap(item);
      summaries[fvInt(row['month'])] = row;
    }
    final months = <int>{...summaries.keys};
    for (final item in effective) {
      final row = fvMap(item);
      final day = DateTime.tryParse(fvText(row['trade_date'], missing: ''));
      if (day != null) months.add(day.month);
    }
    final orderedMonths = months.toList()
      ..sort((left, right) => right.compareTo(left));

    final symbolSummaries = <String, Map<String, dynamic>>{};
    for (final item in symbolSummary) {
      final row = fvMap(item);
      final symbol = fvText(row['symbol'], missing: '');
      if (symbol.isNotEmpty) symbolSummaries[symbol] = row;
    }
    final symbols = <String>{...symbolSummaries.keys};
    for (final item in effective) {
      final symbol = fvText(fvMap(item)['symbol'], missing: '');
      if (symbol.isNotEmpty) symbols.add(symbol);
    }
    final orderedSymbols = symbols.toList()..sort();

    return Column(
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: SegmentedButton<int>(
            key: const Key('ledger-record-grouping'),
            segments: const [
              ButtonSegment(value: 0, label: Text('按月份')),
              ButtonSegment(value: 1, label: Text('按個股')),
            ],
            selected: {recordGrouping},
            onSelectionChanged: (value) =>
                setState(() => recordGrouping = value.first),
            showSelectedIcon: false,
          ),
        ),
        const SizedBox(height: 12),
        if (recordGrouping == 0)
          for (final month in orderedMonths)
            recordGroup(
              key: Key('ledger-month-$month'),
              title: '$yearFilter 年 $month 月',
              realized: realizedPnlLabel(summaries[month]),
              realizedAmount: summaries[month]?['realized_pnl'],
              events: effective.where((item) {
                final row = fvMap(item);
                final day =
                    DateTime.tryParse(fvText(row['trade_date'], missing: ''));
                return day?.month == month;
              }).map(fvMap).toList(),
            ),
        if (recordGrouping == 1)
          for (final symbol in orderedSymbols)
            Builder(builder: (context) {
              final summary = symbolSummaries[symbol];
              final symbolEvents = effective
                  .where((item) =>
                      fvText(fvMap(item)['symbol'], missing: '') == symbol)
                  .map(fvMap)
                  .toList();
              final display = summary ??
                  (symbolEvents.isEmpty
                      ? <String, dynamic>{'symbol': symbol}
                      : symbolEvents.first);
              return recordGroup(
                key: Key('ledger-symbol-$symbol'),
                title: legacy.stockDisplayName(display),
                realized: realizedPnlLabel(summary),
                realizedAmount: summary?['realized_pnl'],
                events: symbolEvents,
              );
            }),
      ],
    );
  }

  Widget reports(
    List<dynamic> pnl,
    List<dynamic> performance, {
    required List<dynamic> monthly,
    required String ytd,
  }) {
    final emptyPnlMessage = switch (ytd) {
      '0' => '本年度確認無交易；已實現損益 0',
      '待更新／尚未確認' => '本年已實現損益仍待 Private Mart 更新',
      _ => '本年已實現損益目前無法確認',
    };
    if (pnl.isEmpty && performance.isEmpty) {
      return fvBoundedState(emptyPnlMessage);
    }
    return Column(
      children: [
        FvMonthlyPnlChart(rows: monthly),
        if (pnl.isEmpty) fvBoundedState(emptyPnlMessage),
        for (final item in pnl)
          Builder(builder: (context) {
            final row = fvMap(item);
            return fvPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${fvText(row['currency'], missing: 'TWD')} · 本年損益',
                    style: const TextStyle(
                      color: fvInk,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '已實現損益 ${legacy.accountingNumber(row['realized_pnl'])}',
                    style: TextStyle(
                      color: fvSignedColor(row['realized_pnl']),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text('股利收入 ${legacy.accountingNumber(row['cash_dividends'])}'),
                  Text(
                    '手續費 ${legacy.accountingNumber(row['fees'])} · 稅 ${legacy.accountingNumber(row['taxes'])}',
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '資料日期 ${fvText(row['valuation_date'])}',
                    style: const TextStyle(color: fvMuted, fontSize: 11),
                  ),
                ],
              ),
            );
          }),
        for (final item in performance)
          Builder(builder: (context) {
            final row = fvMap(item);
            final status = row['xirr_status'];
            return fvPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '年度績效',
                    style: TextStyle(
                      color: fvInk,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    status == 'available' && row['xirr'] != null
                        ? 'XIRR ${legacy.portfolioReturnLabel(row['xirr'])}'
                        : 'XIRR ${legacy.uiLabel(status ?? 'insufficient_data')}',
                    style: status == 'available' && row['xirr'] != null
                        ? TextStyle(
                            color: fvSignedColor(row['xirr']),
                            fontWeight: FontWeight.w700,
                          )
                        : null,
                  ),
                  Text(
                    '資料日期 ${fvText(row['valuation_date'])}',
                    style: const TextStyle(color: fvMuted, fontSize: 11),
                  ),
                ],
              ),
            );
          }),
      ],
    );
  }

  Widget notes(List<dynamic> values) => Column(
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: addNote,
              icon: const Icon(Icons.add),
              label: const Text('新增筆記'),
            ),
          ),
          if (values.isEmpty) fvBoundedState('目前沒有筆記'),
          for (final item in values)
            Builder(builder: (context) {
              final row = fvMap(item);
              return fvPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      fvText(
                        row['body'] ?? row['text'] ?? row['content'],
                        missing: '筆記內容不可用',
                      ),
                      style: const TextStyle(color: fvInk, height: 1.45),
                    ),
                    if (row['symbol'] != null || row['needs_follow_up'] == true) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 7,
                        runSpacing: 7,
                        children: [
                          if (row['symbol'] != null) fvTag('${row['symbol']}'),
                          if (row['needs_follow_up'] == true) fvTag('待追蹤'),
                        ],
                      ),
                    ],
                  ],
                ),
              );
            }),
        ],
      );

  Widget lazySection(
    Future<List<dynamic>>? future,
    String loading,
    Widget Function(List<dynamic>) builder,
  ) {
    if (future == null) return fvBoundedState(loading);
    return FutureBuilder<List<dynamic>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return fvBoundedState(loading);
        }
        return builder(snapshot.data ?? const <dynamic>[]);
      },
    );
  }

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: fvCanvas,
        child: SafeArea(
          bottom: false,
          child: FutureBuilder<List<dynamic>>(
            future: coreData,
            builder: (context, snapshot) {
              final values =
                  snapshot.data ?? const [null, null, null, null];
              final summary = fvRows(values[0]);
              final currentPnl = fvRows(values[1]);
              final canonicalPositions = fvRows(values[2]);
              final currentHistory = fvRows(values[3]);
              final quotePositions = section == 0 && intraday != null
                  ? fvRows(intraday!['positions'])
                  : const <dynamic>[];
              final positions = section == 0 && intraday != null
                  ? quotePositions
                  : canonicalPositions;
              final quoteSummary = section == 0 && intraday != null
                  ? fvRows(intraday!['items'])
                  : const <dynamic>[];
              final aggregate = section == 0 && intraday != null
                  ? (quoteSummary.isEmpty
                      ? <String, dynamic>{}
                      : fvMap(quoteSummary.first))
                  : summary.isEmpty
                      ? <String, dynamic>{}
                      : fvMap(summary.first);
              final coreLoading =
                  snapshot.connectionState != ConnectionState.done;
              final withheld = aggregate['aggregate_status'] == 'withheld';
              final currency = fvText(aggregate['currency'], missing: 'TWD');
              final marketValue = withheld
                  ? '總額暫不發布'
                  : aggregate.isEmpty
                      ? coreLoading
                          ? '載入中'
                          : '資料不足'
                      : '$currency ${legacy.accountingNumber(aggregate['market_value'], missing: '資料不足')}';
              final unrealized = withheld
                  ? '總額暫不發布'
                  : aggregate.isEmpty
                      ? coreLoading
                          ? '載入中'
                          : '資料不足'
                      : '$currency ${legacy.accountingNumber(aggregate['unrealized_pnl'], missing: '資料不足')}';
              final unrealizedReturn = withheld
                  ? '總額暫不發布'
                  : aggregate.isEmpty
                      ? coreLoading
                          ? '載入中'
                          : '資料不足'
                      : legacy.portfolioReturnLabel(
                          aggregate['unrealized_return'],
                        );
              final pnlUnavailable = values[1] == null;
              final historyUnavailable = values[3] == null;
              final ytd = coreLoading
                  ? '載入中'
                  : pnlUnavailable || historyUnavailable
                      ? '資料不足'
                      : currentPnl.isNotEmpty
                          ? currentPnl.length == 1
                              ? '${fvText(fvMap(currentPnl.first)['currency'], missing: 'TWD')} ${legacy.accountingNumber(fvMap(currentPnl.first)['realized_pnl'])}'
                              : '多幣別'
                          : currentHistory.isNotEmpty
                              ? '待更新／尚未確認'
                              : '0';
              final ytdAmount = currentPnl.length == 1
                  ? fvMap(currentPnl.first)['realized_pnl']
                  : null;
              final affected = fvRows(aggregate['affected_symbols']);

              return ListView(
                key: const Key('final-ledger-scroll'),
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: fvPageTitle(
                          context,
                          '記帳／筆記',
                          subtitle: '持股、交易與正式報表使用同一資料語意',
                        ),
                      ),
                      IconButton(
                        onPressed: reload,
                        tooltip: '重新整理',
                        icon: const Icon(Icons.refresh, color: fvTeal),
                      ),
                    ],
                  ),
                  metricGrid(
                    marketValue: marketValue,
                    unrealized: unrealized,
                    unrealizedReturn: unrealizedReturn,
                    ytd: ytd,
                    unrealizedAmount: aggregate['unrealized_pnl'],
                    unrealizedReturnAmount: aggregate['unrealized_return'],
                    ytdAmount: ytdAmount,
                    aggregate: aggregate,
                    withheld: withheld,
                  ),
                  if (ytd == '待更新／尚未確認')
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton.icon(
                        key: const Key('recalculate-pnl'),
                        onPressed: pnlRecalcBusy ? null : recalculatePnl,
                        icon: const Icon(Icons.calculate_outlined, size: 18),
                        label: Text(
                          pnlRecalcBusy ? '重新計算中' : '重新計算損益',
                        ),
                      ),
                    ),
                  if (withheld)
                    fvBoundedState(
                      '正式總額暫不發布${affected.isEmpty ? '' : ' · 受影響 ${affected.join('、')}'}；持股 operational shares／cost 仍可顯示。',
                    ),
                  const SizedBox(height: 12),
                  SegmentedButton<int>(
                    segments: const [
                      ButtonSegment(value: 0, label: Text('持股')),
                      ButtonSegment(value: 1, label: Text('紀錄')),
                      ButtonSegment(value: 2, label: Text('報表')),
                      ButtonSegment(value: 3, label: Text('筆記')),
                    ],
                    selected: {section},
                    onSelectionChanged: (value) {
                      final next = value.first;
                      quoteGeneration++;
                      quoteBusy = false;
                      quoteTimer?.cancel();
                      setState(() {
                        section = next;
                        sectionData =
                            next == 0 ? null : loadSection(next, yearFilter);
                      });
                      if (next == 0) {
                        WidgetsBinding.instance.addPostFrameCallback((_) {
                          if (mounted) startQuotes();
                        });
                      }
                    },
                    showSelectedIcon: false,
                  ),
                  const SizedBox(height: 12),
                  if (section == 0) ...[
                    fvSectionTitle(context, '持股'),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        OutlinedButton.icon(
                          onPressed: quoteBusy
                              ? null
                              : () => refreshQuotes(force: true),
                          icon: const Icon(Icons.refresh, size: 18),
                          label: Text(
                            quoteBusy ? '更新中' : '更新持股股價',
                          ),
                        ),
                        FilledButton.icon(
                          onPressed: addTrade,
                          icon: const Icon(Icons.add, size: 18),
                          label: const Text('新增交易'),
                          style: FilledButton.styleFrom(
                            backgroundColor: fvTeal,
                          ),
                        ),
                      ],
                    ),
                    if (intraday != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        '最新行情 · ${fvText(intraday!['checked_at'])} · ${intraday!['session'] == 'regular' ? '盤中' : intraday!['session'] == 'closing_pending_eod' ? '收盤待正式資料' : '正式／休市'}',
                        style: const TextStyle(
                          color: fvMuted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                    if (quoteError != null) ...[
                      const SizedBox(height: 8),
                      fvBoundedState(quoteError!),
                    ],
                    const SizedBox(height: 8),
                    if (coreLoading && intraday == null)
                      fvBoundedState('持股資料載入中')
                    else
                      holdings(positions),
                  ],
                  if (section == 1) ...[
                    fvSectionTitle(
                      context,
                      '紀錄',
                      trailing: '$yearFilter 年',
                    ),
                    lazySection(sectionData, '紀錄載入中', (detail) {
                      final history =
                          fvRows(detail.isNotEmpty ? detail[0] : null);
                      final monthly =
                          fvRows(detail.length > 1 ? detail[1] : null);
                      final symbolSummary =
                          fvRows(detail.length > 2 ? detail[2] : null);
                      final annualPnl = detail.length > 3 ? detail[3] : null;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(
                            spacing: 10,
                            runSpacing: 8,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              yearSelector(),
                              fvTag(
                                annualRealizedPnlLabel(annualPnl, history),
                                color: fvRows(annualPnl).length == 1
                                    ? fvSignedColor(
                                        fvMap(fvRows(annualPnl).first)['realized_pnl'],
                                      )
                                    : null,
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          records(history, monthly, symbolSummary),
                        ],
                      );
                    }),
                  ],
                  if (section == 2) ...[
                    fvSectionTitle(
                      context,
                      '報表',
                      trailing: '$yearFilter 年',
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: yearSelector(),
                    ),
                    const SizedBox(height: 10),
                    lazySection(sectionData, '報表載入中', (detail) {
                      final reportPnl =
                          fvRows(detail.isNotEmpty ? detail[0] : null);
                      final performance =
                          fvRows(detail.length > 1 ? detail[1] : null);
                      final monthly =
                          fvRows(detail.length > 2 ? detail[2] : null);
                      final history =
                          fvRows(detail.length > 3 ? detail[3] : null);
                      final selectedYtd = yearFilter == DateTime.now().year
                          ? ytd
                          : reportPnl.isNotEmpty
                              ? reportPnl.length == 1
                                  ? '${fvText(fvMap(reportPnl.first)['currency'], missing: 'TWD')} ${legacy.accountingNumber(fvMap(reportPnl.first)['realized_pnl'])}'
                                  : '多幣別'
                              : history.isNotEmpty
                                  ? '待更新／尚未確認'
                                  : '0';
                      return reports(
                        reportPnl,
                        performance,
                        monthly: monthly,
                        ytd: selectedYtd,
                      );
                    }),
                  ],
                  if (section == 3) ...[
                    fvSectionTitle(context, '筆記'),
                    lazySection(sectionData, '筆記載入中', (detail) {
                      final noteRows =
                          fvRows(detail.isNotEmpty ? detail[0] : null);
                      return notes(noteRows);
                    }),
                  ],
                ],
              );
            },
          ),
        ),
      );
}
