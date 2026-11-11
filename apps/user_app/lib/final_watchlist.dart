import 'dart:async';

import 'package:flutter/material.dart';

import 'final_perf.dart';
import 'final_visual_series.dart';
import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalWatchlistPage extends StatefulWidget {
  const FinalWatchlistPage(this.api, {this.onOpenStock, this.active = true, super.key});

  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;
  final bool active;

  @override
  State<FinalWatchlistPage> createState() => _FinalWatchlistPageState();
}

class _FinalWatchlistPageState extends State<FinalWatchlistPage> with WidgetsBindingObserver {
  late Future<dynamic> data;
  dynamic lastGoodData;
  int loadGeneration = 0;
  Future<dynamic>? pendingLoad;
  Timer? quoteTimer;
  bool foreground = true;
  int watchTab = 0; // 0: minute change; 1: formal EOD series
  int historyDays = 20;
  bool managing = false;
  String? selectedSymbol;
  String? historySymbol;
  Future<dynamic>? minutes;
  Future<dynamic>? history;
  final Set<String> backfillAttempts = <String>{};
  final Set<String> backfillInFlight = <String>{};
  final Map<String, String> backfillStatuses = <String, String>{};
  final Map<String, DateTime> manualBackfillAt = <String, DateTime>{};

  Future<dynamic> _readMinutes(String symbol) =>
      widget.api.get('/api/v1/me/watchlist/intraday?symbol=$symbol')
          .timeout(const Duration(seconds: 15));

  Future<dynamic> _readHistory(String symbol) =>
      widget.api.get('/api/v1/public/kline/$symbol?limit=120')
          .timeout(const Duration(seconds: 20));

  void selectSymbol(String symbol) {
    if (selectedSymbol == symbol) return;
    setState(() {
      selectedSymbol = symbol;
      if (watchTab == 0) {
        minutes = _readMinutes(symbol);
      } else {
        historySymbol = symbol;
        history = _readHistory(symbol);
      }
    });
    if (watchTab == 0) requestBackfill(symbol);
  }

  void switchTab(int tab) {
    if (watchTab == tab) return;
    quoteTimer?.cancel();
    setState(() {
      watchTab = tab;
      if (selectedSymbol != null) {
        if (tab == 0) {
          minutes = _readMinutes(selectedSymbol!);
        } else if (historySymbol != selectedSymbol || history == null) {
          historySymbol = selectedSymbol;
          history = _readHistory(selectedSymbol!);
        }
      }
    });
    if (tab == 0) {
      reload(force: false);
      _startQuoteTimer();
      if (selectedSymbol != null) requestBackfill(selectedSymbol!);
    }
  }

  void requestBackfill(String symbol, {bool manual = false}) {
    // Event-demanded only: not called in 60s quote timer.
    if (!widget.active || !foreground || watchTab != 0) return;
    final now = DateTime.now().toUtc().add(const Duration(hours: 8));
    final minute = now.hour * 60 + now.minute;
    if (now.weekday > DateTime.friday || minute < 560) return;
    final slot = ((minute - 540) ~/ 30).clamp(0, 9);
    final key = now.year.toString() + '-' + now.month.toString() +
        '-' + now.day.toString() + '/' + symbol + '/' + slot.toString();
    if (backfillInFlight.contains(symbol)) return;
    if (manual) {
      final now = DateTime.now();
      final last = manualBackfillAt[symbol];
      if (last != null && now.difference(last) < const Duration(minutes: 5)) return;
      manualBackfillAt[symbol] = now;
    } else if (!backfillAttempts.add(key)) {
      return;
    }
    unawaited(_backfill(symbol));
  }

  Future<void> _backfill(String symbol) async {
    backfillInFlight.add(symbol);
    try {
      final result = fvMap(await widget.api.post(
        '/api/v1/me/market/minute-backfill', {'symbol': symbol})
        .timeout(const Duration(seconds: 26)));
      if (!mounted || selectedSymbol != symbol || watchTab != 0) return;
      // Even a throttled or failed broker call may have stored observations
      // from another tab or an in-flight shared request. Re-read PG only.
      setState(() {
        backfillStatuses[symbol] = fvText(result['status'], missing: 'unavailable');
        minutes = _readMinutes(symbol);
      });
    } catch (_) {
      if (mounted) setState(() => backfillStatuses[symbol] = 'unavailable');
    } finally {
      backfillInFlight.remove(symbol);
      if (mounted && selectedSymbol == symbol && watchTab == 0) setState(() {});
    }
  }

  bool get marketHours {
    final taipei = DateTime.now().toUtc().add(const Duration(hours: 8));
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 540 && minutes < 810;
  }

  bool get quotesActive =>
      widget.active && foreground && watchTab == 0 &&
      (ModalRoute.of(context)?.isCurrent ?? true);

  @override
  void initState() {
    super.initState();
    // Avoid triggering the GET -> BackgroundTasks quote refresh while this
    // IndexedStack tab has never been opened.
    data = widget.active ? _load() : Future<dynamic>.value(null);
    WidgetsBinding.instance.addObserver(this);
    foreground = WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _startQuoteTimer();
    });
  }

  void _startQuoteTimer() {
    quoteTimer?.cancel();
    if (quotesActive && marketHours) {
      quoteTimer = Timer.periodic(const Duration(minutes: 1), (_) {
        if (!quotesActive || !marketHours) {
          quoteTimer?.cancel();
        } else {
          reload(force: false);
        }
      });
    }
  }

  @override
  void didUpdateWidget(FinalWatchlistPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.api, widget.api)) {
      // Owner/API token transitions must never reuse another owner's snapshot.
      lastGoodData = null;
      selectedSymbol = null;
      historySymbol = null;
      minutes = null;
      history = null;
      backfillAttempts.clear();
      backfillInFlight.clear();
      backfillStatuses.clear();
      manualBackfillAt.clear();
      data = widget.active ? _load(force: true) : Future<dynamic>.value(null);
    }
    if (oldWidget.active != widget.active) {
      if (widget.active) {
        if (watchTab == 0) {
          reload(force: false);
          if (selectedSymbol != null) requestBackfill(selectedSymbol!);
        }
        _startQuoteTimer();
      } else {
        quoteTimer?.cancel();
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground) {
      if (widget.active) {
        if (watchTab == 0) {
          reload(force: false);
          if (selectedSymbol != null) requestBackfill(selectedSymbol!);
        }
        _startQuoteTimer();
      }
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

  Future<dynamic> _load({bool force = false}) {
    if (!force && pendingLoad != null) return pendingLoad!;
    late final Future<dynamic> request;
    request = _read().whenComplete(() {
      if (identical(pendingLoad, request)) pendingLoad = null;
    });
    pendingLoad = request;
    return request;
  }

  Future<dynamic> _read() async {
    final generation = ++loadGeneration;
    final stopwatch = Stopwatch()..start();
    try {
      final response = await widget.api.get('/api/v1/me/watchlist')
          // Allow bounded mobile latency; 9s caused false failures even when
          // the authenticated Owner endpoint eventually returned HTTP 200.
          .timeout(const Duration(seconds: 25));
      if (generation != loadGeneration || !mounted) return null;
      lastGoodData = response;
      if (response is List) {
        final symbols = fvRows(response).map(fvMap)
            .map((row) => fvText(row['symbol'], missing: '')).toList();
        if (!symbols.contains(selectedSymbol)) {
          selectedSymbol = symbols.isEmpty ? null : symbols.first;
          minutes = null;
          history = null;
          historySymbol = null;
          if (selectedSymbol != null) {
            if (watchTab == 0) {
              minutes = _readMinutes(selectedSymbol!);
              requestBackfill(selectedSymbol!);
            } else {
              historySymbol = selectedSymbol;
              history = _readHistory(selectedSymbol!);
            }
          }
        } else if (selectedSymbol != null && watchTab == 0) {
          // No upstream provider call on minute-chart read: cached PG only.
          minutes = _readMinutes(selectedSymbol!);
        }
      }
      return response;
    } finally {
      stopwatch.stop();
      FinalPerf.recordCore('watchlist', stopwatch.elapsed);
    }
  }

  void reload({bool force = true}) =>
      setState(() { data = _load(force: force); });

  Future<void> add() async {
    final query = await legacy.textDialog(
      context,
      '搜尋關注股票',
      '股票代號或中文名稱',
      confirmLabel: '搜尋',
    );
    if (query == null || query.trim().isEmpty) return;
    try {
      final result = await widget.api.get(Uri(
        path: '/api/v1/me/watchlist/search',
        queryParameters: {'q': query.trim()},
      ).toString());
      if (!mounted) return;
      final matches = fvRows(result);
      final symbol = await showDialog<String>(
        context: context,
        builder: (context) => SimpleDialog(
          title: const Text('選擇股票'),
          children: [
            if (matches.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('沒有符合的股票'),
              ),
            for (final item in matches)
              SimpleDialogOption(
                onPressed: () =>
                    Navigator.pop(context, fvText(fvMap(item)['symbol'])),
                child: Text(legacy.stockDisplayName(fvMap(item))),
              ),
          ],
        ),
      );
      if (symbol == null || !mounted) return;
      final target = await legacy.textDialog(context, '設定目標價', '可留空');
      await widget.api.post('/api/v1/me/watchlist', {
        'symbol': symbol,
        if (target?.trim().isNotEmpty == true) 'target_price': target!.trim(),
      });
      reload();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('關注已保存，分析快照將於背景更新')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('目前無法加入關注')),
        );
      }
    }
  }

  Future<void> reorder(List<dynamic> rows, int oldIndex, int newIndex) async {
    if (newIndex > oldIndex) newIndex -= 1;
    final reordered = List<dynamic>.from(rows);
    final moved = reordered.removeAt(oldIndex);
    reordered.insert(newIndex, moved);
    var version = 0;
    for (final item in rows) {
      final value = fvInt(fvMap(item)['version']);
      if (value > version) version = value;
    }
    if (version < 1) return;
    try {
      await widget.api.put('/api/v1/me/watchlist/order', {
        'symbols': [for (final item in reordered) fvMap(item)['symbol']],
        'expected_version': version,
      });
      reload();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('排序已保存，分析快照將於背景更新')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('排序未更新，請重新整理')),
        );
      }
    }
  }

  Future<void> editPool(Map<String, dynamic> row) async {
    var tier = '${row['tier'] ?? 'C'}';
    var locked = row['sync_locked'] == true;
    final save = await showDialog<bool>(context: context, builder: (context) => StatefulBuilder(
      builder: (context, update) => AlertDialog(title: Text('${row['symbol']} 觀察池'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          DropdownButton<String>(value: tier, isExpanded: true,
            items: ['A', 'B', 'C'].map((v) => DropdownMenuItem(value: v, child: Text('$v 池'))).toList(),
            onChanged: (v) => update(() => tier = v!)),
          CheckboxListTile(title: const Text('鎖定，不被週批調整'), value: locked,
            onChanged: (v) => update(() => locked = v!)),
          if (row['tier_confirmed'] != true) const Text('原名單暫列C，請確認分類；不影響原資料。'),
        ]), actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('儲存'))])));
    if (save != true || !mounted) return;
    try {
      await widget.api.put('/api/v1/me/personal-strategy/watchlist/${Uri.encodeComponent('${row['symbol']}')}',
        {'tier': tier, 'locked': locked, 'expected_version': row['version']});
      reload();
    } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
  }


  Widget _tabs() => Row(children: [
    Expanded(child: FilledButton(
      key: const Key('watch-tab-live'), onPressed: () => switchTab(0),
      style: FilledButton.styleFrom(
        backgroundColor: watchTab == 0 ? fvTeal : fvSoft,
        foregroundColor: watchTab == 0 ? Colors.white : fvInk),
      child: const Text('盤中變化'),
    )),
    const SizedBox(width: 9),
    Expanded(child: FilledButton(
      key: const Key('watch-tab-longterm'), onPressed: () => switchTab(1),
      style: FilledButton.styleFrom(
        backgroundColor: watchTab == 1 ? fvTeal : fvSoft,
        foregroundColor: watchTab == 1 ? Colors.white : fvInk),
      child: const Text('長期觀察'),
    )),
  ]);


  // One compact selector, shared across intraday and long-horizon views.
  Widget _selector(List<dynamic> rows) {
    final list = rows.map(fvMap).toList();
    final symbols = list.map((row) => fvText(row['symbol'])).toList();
    final index = symbols.indexOf(selectedSymbol ?? '');
    final active = index < 0 ? list.first : list[index];
    return Material(color: Colors.transparent, child: Row(children: [
      IconButton(
        key: const Key('watch-previous-stock'),
        tooltip: '上一檔關注股',
        onPressed: index > 0 ? () => selectSymbol(symbols[index - 1]) : null,
        icon: const Icon(Icons.chevron_left, size: 26),
      ),
      Expanded(child: PopupMenuButton<String>(
        key: const Key('watch-stock-picker'),
        tooltip: '選擇關注股票',
        onSelected: selectSymbol,
        itemBuilder: (context) => [
          for (final row in list)
            PopupMenuItem<String>(
              key: Key('watch-select-${fvText(row['symbol'])}'),
              value: fvText(row['symbol']),
              child: Row(children: [
                Text('${fvText(row['tier'], missing: 'C')} · ',
                  style: const TextStyle(color: fvTeal, fontSize: 14)),
                Expanded(child: Text('${fvText(row['symbol'])} ${fvText(row['stock_name'], missing: '')}',
                    style: const TextStyle(fontSize: 16),
                    maxLines: 1, overflow: TextOverflow.ellipsis)),
                if (selectedSymbol == row['symbol'])
                  const Icon(Icons.check, color: fvTeal, size: 18),
              ]),
            ),
        ],
        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Flexible(child: Text('${fvText(active['symbol'])} ${fvText(active['stock_name'], missing: '')}',
            overflow: TextOverflow.ellipsis, maxLines: 1,
            style: const TextStyle(color: fvInk, fontSize: 18, fontWeight: FontWeight.w800))),
          const Icon(Icons.arrow_drop_down, color: fvTeal),
        ]),
      )),
      IconButton(
        key: const Key('watch-next-stock'),
        tooltip: '下一檔關注股',
        onPressed: index >= 0 && index < symbols.length - 1
            ? () => selectSymbol(symbols[index + 1]) : null,
        icon: const Icon(Icons.chevron_right, size: 26),
      ),
    ]));
  }

  Widget _selectedSummary(Map<String, dynamic> row) {
    final symbol = fvText(row['symbol']);
    final priceStatus = fvText(row['price_status'], missing: 'missing');
    final fresh = priceStatus == 'available' && row['quote_state'] == 'intraday';
    final validChange = priceStatus == 'available' &&
        row['change'] != null && row['change_percent'] != null;
    return fvPanel(child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Expanded(child: Text(legacy.stockDisplayName(row),
            key: const Key('watch-selected-stock'),
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: fvInk, fontSize: 17, fontWeight: FontWeight.w800))),
          fvStatusPill(priceStatus),
        ]),
        const SizedBox(height: 5),
        Row(children: [
          Expanded(child: fvLimitPriceText(row,
            legacy.accountingNumber(row['market_price'], decimals: 2,
                missing: '行情尚未取得'),
            key: const Key('watch-selected-price'), fontSize: 28,
            ordinaryColor: validChange ? fvSignedColor(row['change']) : fvInk)),
          if (validChange)
            Text('${legacy.accountingNumber(row['change'], decimals: 2)}  '
                '${fvSignedPercent(row['change_percent'])}',
              key: Key('watch-price-change-$symbol'),
              style: TextStyle(color: fvSignedColor(row['change']),
                  fontSize: 16, fontWeight: FontWeight.w800)),
        ]),
        const SizedBox(height: 4),
        Text('${fresh ? '盤中' : '非即時'} · 價格日 ${fvText(row['price_date'], missing: '缺值')}'
            ' · 前收 ${legacy.accountingNumber(row['previous_close'], decimals: 2)}',
          key: const Key('watch-quote-status'),
          style: const TextStyle(color: fvMuted, fontSize: 13)),
        if (row['held'] == true || row['in_market'] == false)
          Padding(padding: const EdgeInsets.only(top: 5),
            child: Wrap(spacing: 6, runSpacing: 4, children: [
              if (row['held'] == true) fvTag('已持有'),
              if (row['in_market'] == false)
                fvTag('已退出有效名冊 · 仍保留關注', warning: true),
            ]),
          ),
      ],
    ));
  }

  // Less frequent pool management, tags and links belong below the chart.
  Widget _selectedMetadata(Map<String, dynamic> row) => Material(
    color: Colors.transparent,
    child: ExpansionTile(
    key: const Key('watch-more-info'),
    title: const Text('觀察設定與更多狀態',
      style: TextStyle(color: fvInk, fontWeight: FontWeight.w800, fontSize: 15)),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
    children: [
      Wrap(spacing: 6, runSpacing: 6, children: [
        fvTag(row['held'] == true ? 'S 持股' : '${fvText(row['tier'], missing: 'C')} 池'),
        if (row['tier_confirmed'] != true) fvTag('待確認分類'),
        if (row['sync_locked'] == true) fvTag('已鎖定'),
        fvTag('來源 ${fvText(row['price_source'], missing: '待取得')}'),
        fvTag(row['target_price'] == null ? '目標價未設定'
            : '目標 ${legacy.accountingNumber(row['target_price'], decimals: 2)}'),
        if (fvInt(row['pending_note_count']) > 0)
          fvTag('待追蹤 ${fvInt(row['pending_note_count'])}'),
      ]),
      Wrap(spacing: 6, children: [
        if (widget.onOpenStock != null)
          TextButton.icon(
            onPressed: () => widget.onOpenStock?.call(fvText(row['symbol'])),
            icon: const Icon(Icons.open_in_new, size: 18),
            label: const Text('個股詳情')),
        TextButton.icon(onPressed: () => editPool(row),
          icon: const Icon(Icons.tune, size: 18),
          label: const Text('觀察池設定')),
      ]),
    ],
  ));

  Widget _intradayChart(String symbol) => FutureBuilder<dynamic>(
    key: ValueKey('watch-minute-future-$symbol'),
    future: minutes,
    builder: (context, state) {
      if (state.connectionState != ConnectionState.done) {
        return fvBoundedState('關注股分鐘資料載入中');
      }
      if (state.hasError || state.data == null) {
        return fvBoundedState('分鐘資料尚無法讀取；不以舊行情冒充即時');
      }
      final root = fvMap(state.data);
      final today = fvText(root['as_of'], missing: '');
      final referenceDate = fvText(root['previous_close_date'], missing: '');
      final previousClose = root['previous_close_source'] ==
              'official_previous_close' &&
          today.isNotEmpty && referenceDate.isNotEmpty &&
          referenceDate.compareTo(today) < 0
              ? fvNumber(root['previous_close']) : null;
      return Column(children: [
        FvIntradayProgressChart(
          key: ValueKey('watch-minute-chart-$symbol'),
          rows: fvRows(root['items']),
          label: '$symbol · 今日分鐘走勢',
          unit: '元／股', height: 205, previousClose: previousClose,
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(4, 0, 4, 8),
          child: Text('固定 09:00–13:30；分鐘線僅顯示實際資料，不補虛構點。',
            style: TextStyle(color: fvMuted, fontSize: 11)),
        ),
        if (backfillInFlight.contains(symbol))
          const Text('正在查詢歷史 1 分 K（非即時行情）…',
            style: TextStyle(color: fvMuted, fontSize: 11))
        else if (backfillStatuses[symbol] != null)
          Padding(padding: const EdgeInsets.only(top: 3), child: Row(children: [
            Expanded(child: Text(switch (backfillStatuses[symbol]) {
              'available' => '已讀回券商歷史 1 分 K',
              'cached_or_throttled' => '回補額度暫未開放；顯示已保存的分鐘點',
              'missing' => '券商尚無歷史 K 棒；顯示已保存的分鐘點',
              _ => '券商歷史 K 棒暫不可用；顯示已保存的分鐘點',
            }, style: const TextStyle(color: fvMuted, fontSize: 11))),
            TextButton(
              onPressed: () => requestBackfill(symbol, manual: true),
              child: const Text('重查缺口', style: TextStyle(fontSize: 12))),
          ])),
      ]);
    },
  );

  Widget _historyChart(String symbol) => Column(children: [
    fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('正式歷史收盤價',
          style: TextStyle(color: fvInk, fontSize: 16,
            fontWeight: FontWeight.w800)),
        const SizedBox(height: 3),
        const Text('與盤中分鐘點分開；原始日收盤未還原除權息。',
          style: TextStyle(color: fvMuted, fontSize: 11)),
        const SizedBox(height: 8),
        Wrap(spacing: 7, runSpacing: 4, children: [
          for (final days in const [5, 20, 60, 120])
            ChoiceChip(
              key: Key('watch-history-$days'),
              visualDensity: VisualDensity.compact,
              label: Text('近$days日'),
              selected: historyDays == days,
              onSelected: (_) => setState(() => historyDays = days),
            ),
        ]),
      ])),
    FutureBuilder<dynamic>(
      key: ValueKey('watch-history-future-$symbol'),
      future: history,
      builder: (context, state) {
        if (state.connectionState != ConnectionState.done)
          return fvBoundedState('正式歷史收盤載入中');
        if (state.hasError || state.data == null)
          return fvBoundedState('正式日收盤暫時無法取得');
        final series = fvRows(state.data).map(fvMap).map((row) =>
          <String, dynamic>{'date': row['trade_date'], 'value': row['close']}
        ).where((point) => fvText(point['date'], missing: '').isNotEmpty).toList();
        series.sort((a, b) => fvText(a['date']).compareTo(fvText(b['date'])));
        final visible = series.length > historyDays
            ? series.sublist(series.length - historyDays) : series;
        if (visible.length < 2)
          return fvBoundedState('有效日收盤少於兩期，無法繪製長期趨勢');
        return FvVisualSeriesChart(
          key: ValueKey('watch-history-chart-$symbol-$historyDays'),
          rows: visible,
          label: '$symbol · 近$historyDays日收盤',
          unit: '元／股', height: 205, showTable: false, dailyTable: true,
        );
      },
    ),
  ]);

  Widget _selectedContent(List<dynamic> rows) {
    if (rows.isEmpty) return const SizedBox.shrink();
    final selected = rows.map(fvMap).firstWhere(
      (row) => fvText(row['symbol']) == selectedSymbol,
      orElse: () => fvMap(rows.first),
    );
    final symbol = fvText(selected['symbol']);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _selector(rows),
      _selectedSummary(selected),
      if (watchTab == 0) _intradayChart(symbol)
      else _historyChart(symbol),
      _selectedMetadata(selected),
      fvPanel(padding: EdgeInsets.zero, child: ListTile(
        key: const Key('watch-manage-toggle'),
        title: const Text('管理關注清單',
          style: TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
        subtitle: const Text('展開後可排序、調整及移除；平時不重複顯示大卡片'),
        trailing: Icon(managing ? Icons.expand_less : Icons.expand_more),
        onTap: () => setState(() => managing = !managing),
      )),
    ]);
  }

  Widget header(BuildContext context, int? count, {int followups = 0}) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          fvPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                FilledButton.icon(
                  onPressed: add,
                  icon: const Icon(Icons.search),
                  label: const Text('搜尋股票代號或中文名稱'),
                  style: FilledButton.styleFrom(backgroundColor: fvTeal),
                ),
                const SizedBox(height: 10),
                if (followups > 0) ...[
                  fvTag('待追蹤筆記 $followups', icon: Icons.flag_outlined),
                  const SizedBox(height: 8),
                ],
                Text(
                  '我的關注 ${count?.toString() ?? '—'}/50',
                  style: const TextStyle(
                    color: fvInk,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  '新加入可選上市／上櫃全部個股；既有退出名冊股票仍保留關注。',
                  style: TextStyle(color: fvMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          if (managing)
            fvSectionTitle(context, '我的關注',
              trailing: count == null || count == 0 ? null : '長按拖曳排序'),
        ],
      );

  Widget card(Map<String, dynamic> row) {
    final symbol = fvText(row['symbol']);
    final offUniverse = row['in_market'] == false;
    final pending = fvInt(row['pending_note_count']);
    return Card(
      key: ValueKey('watch-$symbol'),
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 0,
      color: Colors.white,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Ink(
        decoration: fvPastelDecoration(
          tone: offUniverse ? FvCardTone.peach
              : pending > 0 ? FvCardTone.lavender
              : row['held'] == true ? FvCardTone.mint : FvCardTone.sky,
        ),
        child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () => widget.onOpenStock?.call(symbol),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 10, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
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
                        const SizedBox(height: 2),
                        Text(
                          '資料日 ${fvText(row['price_date'], missing: '尚未取得')}',
                          style: const TextStyle(color: fvMuted, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                  IconButton(tooltip: '調整觀察池與鎖定', onPressed: () => editPool(row), icon: Icon(row['sync_locked'] == true ? Icons.lock : Icons.tune)),
                  IconButton(
                    tooltip: '移除關注',
                    onPressed: () async {
                      try {
                        await widget.api.delete(
                          '/api/v1/me/watchlist/${Uri.encodeComponent(symbol)}',
                        );
                        reload();
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('關注已移除，分析快照將於背景更新')),
                          );
                        }
                      } catch (_) {
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('目前無法移除關注')),
                          );
                        }
                      }
                    },
                    icon: const Icon(Icons.close, color: fvMuted),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      legacy.accountingNumber(
                        row['market_price'],
                        decimals: 2,
                        missing: '行情尚未取得',
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: fvSignedColor(row['change']),
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  fvStatusPill(
                    row['price_status'] ??
                        (row['market_price'] == null ? 'partial' : 'available'),
                  ),
                ],
              ),
              if (row['change'] != null && row['change_percent'] != null) ...[
                const SizedBox(height: 3),
                Row(children: [
                  Icon(fvNumber(row['change']) != null && fvNumber(row['change'])! >= 0
                    ? Icons.arrow_upward : Icons.arrow_downward,
                    size: 16, color: fvSignedColor(row['change'])),
                  const SizedBox(width: 4),
                  Text('${legacy.accountingNumber(row['change'], decimals: 2)}  ${fvSignedPercent(row['change_percent'])}',
                    key: Key('watch-price-change-$symbol'),
                    style: TextStyle(color: fvSignedColor(row['change']),
                      fontSize: 15, fontWeight: FontWeight.w800)),
                  const SizedBox(width: 7),
                  Expanded(child: Text('前收 ${legacy.accountingNumber(row['previous_close'], decimals: 2)}',
                    textAlign: TextAlign.end, style: const TextStyle(color: fvMuted, fontSize: 11))),
                ]),
              ],
              const SizedBox(height: 10),
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: [
                  if (row['held'] == true) fvTag('已持有', icon: Icons.account_balance_wallet_outlined),
                  if (row['held'] == true) fvTag('研究 ${row['tier'] ?? 'C'}'),
                  if (row['tier_confirmed'] != true) fvTag('待確認分類'),
                  if (row['sync_locked'] == true) fvTag('已鎖定'),
                  fvTag(row['held'] == true ? 'S 持股' : '${row['tier'] ?? 'C'} 池',
                      icon: row['held'] == true ? Icons.account_balance_wallet_outlined : Icons.bookmark_outline),
                  fvTag(row['target_price'] == null
                      ? '目標價未設定'
                      : '目標 ${legacy.accountingNumber(row['target_price'], decimals: 2)}',
                      icon: Icons.track_changes_outlined),
                  if (pending > 0) fvTag('待追蹤 $pending', icon: Icons.flag_outlined),
                  if (offUniverse)
                    fvTag('已退出有效名冊 · 仍保留關注', warning: true,
                        icon: Icons.bookmark_added_outlined),
                ],
              ),
            ],
          ),
        ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: fvCanvas,
        child: SafeArea(
          bottom: false,
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 8, 14, 4),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  fvPageTitle(context, '關注'),
                  _tabs(),
                ]),
            ),
            Expanded(child: FutureBuilder<dynamic>(
              future: data,
            builder: (context, snapshot) {
              final rows = List<dynamic>.from(fvRows(snapshot.data ?? lastGoodData));
              rows.sort((a,b) { final x = '${fvMap(a)['tier'] ?? 'C'}'.compareTo('${fvMap(b)['tier'] ?? 'C'}'); return x != 0 ? x : fvInt(fvMap(a)['sort_order']).compareTo(fvInt(fvMap(b)['sort_order'])); });
              if (snapshot.connectionState != ConnectionState.done && lastGoodData == null) {
                return ListView(
                  padding: const EdgeInsets.fromLTRB(14, 8, 14, 28),
                  children: [header(context, null), fvBoundedState('關注清單載入中')],
                );
              }
              if (snapshot.hasError && lastGoodData == null) {
                return ListView(
                  padding: const EdgeInsets.fromLTRB(14, 8, 14, 28),
                  children: [
                    header(context, null),
                    fvPanel(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(children: [
                            const Expanded(child: Text('關注清單暫時無法使用')),
                            TextButton(onPressed: reload, child: const Text('重試')),
                          ]),
                          const Text('若持續失敗，請重新開啟 App 登入',
                              style: TextStyle(color: fvMuted, fontSize: 12)),
                        ],
                      ),
                    ),
                  ],
                );
              }
              if (rows.isEmpty) {
                return ListView(
                  padding: const EdgeInsets.fromLTRB(14, 8, 14, 28),
                  children: [header(context, 0), fvBoundedState('目前沒有關注股票')],
                );
              }
              return ReorderableListView.builder(
                key: const Key('final-watchlist-scroll'),
                padding: const EdgeInsets.fromLTRB(14, 8, 14, 28),
                header: Column(children: [
                  _selectedContent(rows),
                  header(context, rows.length, followups: rows.fold<int>(0,
                      (total, row) => total + fvInt(fvMap(row)['pending_note_count']))),
                  if (snapshot.connectionState != ConnectionState.done)
                    fvBoundedState('清單更新中，保留上次有效資料', icon: Icons.sync),
                  if (snapshot.hasError)
                    fvPanel(child: Row(children: [
                      const Expanded(child: Text('更新失敗，顯示上次有效資料')),
                      TextButton(onPressed: reload, child: const Text('重試')),
                    ])),
                ]),
                footer: const SizedBox(height: 8),
                itemCount: managing ? rows.length : 0,
                buildDefaultDragHandles: false,
                onReorder: (oldIndex, newIndex) => reorder(rows, oldIndex, newIndex),
                itemBuilder: (context, index) => ReorderableDelayedDragStartListener(
                  key: ValueKey('watch-${fvMap(rows[index])['symbol']}'),
                  index: index,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    if (index == 0 || fvMap(rows[index])['tier'] != fvMap(rows[index-1])['tier'])
                      Padding(padding: const EdgeInsets.symmetric(vertical: 10), child: Text('${fvMap(rows[index])['tier'] ?? 'C'} 觀察池', style: Theme.of(context).textTheme.titleLarge)),
                    card(fvMap(rows[index])),
                  ]),
                ),
              );
            },
            )),
          ]),
        ),
      );
}
