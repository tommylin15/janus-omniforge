import 'dart:async';

import 'package:flutter/material.dart';

import 'final_perf.dart';
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
  late Future<dynamic> brief;
  late Future<dynamic> personal;
  late Future<dynamic> ownerQuotes;
  Future<dynamic>? stockMinutes;
  String? selectedHolding;
  dynamic lastGoodOwnerQuotes;
  late Future<dynamic> assets;
  Timer? marketTimer;
  bool foreground = true;
  int historyDays = 0;
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
      widget.active && foreground && (ModalRoute.of(context)?.isCurrent ?? true);

  @override
  void initState() {
    super.initState();
    // IndexedStack creates every tab up front. Hidden tabs must not trigger
    // an upstream quote request until the user actually selects this page.
    market = widget.active ? _readCoreMarket() : Future<dynamic>.value(null);
    brief = widget.active ? _read('/api/v1/public/daily-brief') : Future<dynamic>.value(null);
    personal = widget.active ? _read('/api/v1/me/today-relevant') : Future<dynamic>.value(null);
    ownerQuotes = widget.active
        ? market.then((_) => _loadOwnerQuotes())
        : Future<dynamic>.value(null);
    assets = widget.active ? _read('/api/v1/me/portfolio/snapshot') : Future<dynamic>.value(null);
    WidgetsBinding.instance.addObserver(this);
    foreground = WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _startMarketTimer();
    });
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
      lastGoodMarket = null;
      market = widget.active ? _readCoreMarket() : Future<dynamic>.value(null);
      brief = widget.active ? _read('/api/v1/public/daily-brief') : Future<dynamic>.value(null);
      personal = widget.active ? _read('/api/v1/me/today-relevant') : Future<dynamic>.value(null);
      ownerQuotes = widget.active
          ? market.then((_) => _loadOwnerQuotes())
          : Future<dynamic>.value(null);
      assets = widget.active ? _read('/api/v1/me/portfolio/snapshot') : Future<dynamic>.value(null);
    }
    if (oldWidget.active != widget.active) {
      if (widget.active) {
        setState(() {
          market = _loadMarketWithoutPerf();
          brief = _read('/api/v1/public/daily-brief');
          personal = _read('/api/v1/me/today-relevant');
          ownerQuotes = market.then((_) => _loadOwnerQuotes());
          assets = _read('/api/v1/me/portfolio/snapshot');
        });
        _startMarketTimer();
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
          ownerQuotes = market.then((_) => _loadOwnerQuotes());
        });
        _startMarketTimer();
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

  Future<dynamic> _loadOwnerQuotes() async {
    final result = await _read('/api/v1/me/portfolio/quotes',
        timeout: const Duration(seconds: 24));
    if (!mounted || !widget.active || result is! Map) return result;
    if (result['positions'] is List) {
      lastGoodOwnerQuotes = result;
      final positions = fvRows(result['positions']).map(fvMap)
          .where((row) => row['currency'] == 'TWD' && row['symbol'] != null)
          .toList();
      if (selectedHolding == null ||
          !positions.any((row) => row['symbol'] == selectedHolding)) {
        selectedHolding = positions.isEmpty ? null : '${positions.first['symbol']}';
      }
      if (selectedHolding != null) {
        stockMinutes = _read(
          '/api/v1/me/portfolio/intraday?symbol=$selectedHolding');
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

  Widget _taiexTrend(dynamic raw) {
    final section = fvMap(raw);
    final data = fvMap(section['data']);
    final history = fvRows(data['history_points']);
    final intraday = fvRows(data['intraday_points']);
    // No provisional intraday quote, partial period, or sample placeholder
    // may be spliced into this official closing-price chart.
    final usable = history.where((item) {
      final value = fvNumber(fvMap(item)['value']);
      return value != null && value.isFinite && value > 0;
    }).toList();
    if (usable.length < 2 && intraday.length < 2) {
      return fvPanel(child: Row(children: [
        const Icon(Icons.show_chart, color: fvMuted),
        const SizedBox(width: 9),
        const Expanded(child: Text('加權指數歷史走勢尚未就緒',
            style: TextStyle(color: fvMuted))),
      ]));
    }
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
                      Expanded(child: Text(historyDays == 0
                          ? '加權指數 · 今日分鐘觀測' : '加權指數 · 官方收盤走勢',
                        style: TextStyle(color: fvInk, fontWeight: FontWeight.w800))),
                      IconButton(icon: const Icon(Icons.close),
                        tooltip: '關閉大盤走勢', onPressed: () => Navigator.pop(dialogContext)),
                    ]),
                    InteractiveViewer(
                      minScale: 1, maxScale: 3,
                      child: FvVisualSeriesChart(
                        rows: historyDays == 0 ? intraday : usable,
                        label: '加權指數', unit: '點', height: 235,
                        intraday: historyDays == 0, markExtrema: historyDays == 0,
                        dailyTable: historyDays != 0, showTable: historyDays != 0),
                    ),
                  ]),
                ),
              )),
          ),
        ]),
      ),
      Material(color: Colors.transparent, child: Wrap(spacing: 5, children: [
        for (final days in const [0, 5, 20, 30])
          ChoiceChip(
            key: Key('today-trend-$days'),
            visualDensity: VisualDensity.compact,
            label: Text(days == 0 ? '今日盤中' : days == 5 ? '近5日' : days == 20 ? '近20日' : '近30日'),
            selected: historyDays == days,
            onSelected: (_) => setState(() => historyDays = days),
          ),
      ])),
      if (historyDays == 0)
        intraday.length >= 2
          ? FvVisualSeriesChart(rows: intraday, label: '加權指數 · 盤中',
              unit: '點', height: 190, intraday: true,
              markExtrema: true, showTable: false)
          : fvBoundedState('今日盤中資料收集中；僅保留實際取得的分鐘點，不補造缺口')
      else
        FvVisualSeriesChart(rows: shown, label: '加權指數 · 收盤',
            unit: '點', height: 130, dailyTable: true),
      Padding(
        padding: const EdgeInsets.fromLTRB(5, 3, 5, 12),
        child: Text('正式收盤截至 $asOf · 來源 ${sources.isEmpty ? '待查' : sources.join('、')}'
            ' · 盤中資料獨立顯示，不計入正式日收盤',
            style: const TextStyle(fontSize: 11, color: fvMuted)),
      ),
    ]);
  }

  Widget _flowBar(String label, Object? raw, double maxMagnitude,
      {required String unit, bool signed = true}) {
    final amount = fvNumber(raw);
    if (amount == null || !amount.isFinite) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Text('$label　資料缺漏', style: const TextStyle(color: fvMuted)),
      );
    }
    final rising = amount > 0;
    final falling = amount < 0;
    final color = !signed ? fvTeal : rising ? fvGain : falling ? fvLoss : fvMuted;
    final marker = !signed ? '' : rising ? '▲' : falling ? '▼' : '—';
    final width = maxMagnitude > 0
        ? (amount.abs() / maxMagnitude).clamp(0.0, 1.0) : 0.0;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(label, style: const TextStyle(
              fontWeight: FontWeight.w600, color: fvInk))),
          Flexible(child: Text(
              '$marker ${legacy.accountingNumber(amount, decimals: 0)} $unit',
              textAlign: TextAlign.end,
              style: TextStyle(color: color, fontSize: 12,
                  fontWeight: FontWeight.w700))),
        ]),
        const SizedBox(height: 5),
        Semantics(label: '$label，$marker ${legacy.accountingNumber(amount, decimals: 0)} $unit',
          child: LinearProgressIndicator(
            minHeight: 7, borderRadius: BorderRadius.circular(5),
            value: width, backgroundColor: fvSoft, color: color,
          )),
      ]),
    );
  }

  Widget _institutionalVisual(dynamic raw) {
    final section = fvMap(raw);
    final data = fvMap(section['data']);
    const fields = ['foreign_net_shares',
      'investment_trust_net_shares', 'dealer_net_shares'];
    final values = fields.map((key) => fvNumber(data[key]))
        .whereType<double>().where((v) => v.isFinite).toList();
    final maximum = values.isEmpty ? 0.0 :
        values.map((value) => value.abs()).reduce((a, b) => a > b ? a : b);
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Icon(Icons.groups_2_outlined, color: fvTeal),
        const SizedBox(width: 8),
        const Expanded(child: Text('法人動向',
            style: TextStyle(color: fvInk, fontSize: 17, fontWeight: FontWeight.w800))),
        fvStatusPill(section['status'] ?? 'missing'),
      ]),
      const SizedBox(height: 5),
      const Text('三大法人當日買賣超 · 股數（長條為相對幅度）',
          style: TextStyle(fontSize: 11, color: fvMuted)),
      _flowBar('外資', data['foreign_net_shares'], maximum, unit: '股'),
      _flowBar('投信', data['investment_trust_net_shares'], maximum, unit: '股'),
      _flowBar('自營商', data['dealer_net_shares'], maximum, unit: '股'),
      if (_freshness(section).isNotEmpty)
        Text(_freshness(section), style: const TextStyle(color: fvMuted, fontSize: 11)),
    ]));
  }

  Widget _marketActivityVisual(dynamic raw) {
    final section = fvMap(raw);
    final data = fvMap(section['data']);
    final buy = fvNumber(data['day_trade_buy_twd']);
    final sell = fvNumber(data['day_trade_sell_twd']);
    final values = [buy, sell].whereType<double>().where((v) => v.isFinite).toList();
    final maximum = values.isEmpty ? 0.0 :
        values.map((v) => v.abs()).reduce((a, b) => a > b ? a : b);
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Icon(Icons.bar_chart, color: fvTeal),
        const SizedBox(width: 8),
        const Expanded(child: Text('市場活動',
            style: TextStyle(color: fvInk, fontSize: 17, fontWeight: FontWeight.w800))),
        fvStatusPill(section['status'] ?? 'missing'),
      ]),
      const SizedBox(height: 6),
      const Text('當沖交易（買賣金額／股數，均為官方欄位）',
          style: TextStyle(fontSize: 11, color: fvMuted)),
      if (data['day_trade_shares'] != null) ...[
        const SizedBox(height: 8),
        Text('當沖股數',
            style: const TextStyle(color: fvMuted, fontSize: 12)),
        Text('${legacy.accountingNumber(data['day_trade_shares'], decimals: 0)} 股',
            style: const TextStyle(color: fvInk, fontSize: 21,
              fontWeight: FontWeight.w800)),
      ],
      _flowBar('當沖買進', buy, maximum, unit: 'TWD', signed: false),
      _flowBar('當沖賣出', sell, maximum, unit: 'TWD', signed: false),
      if (_freshness(section).isNotEmpty)
        Text(_freshness(section), style: const TextStyle(color: fvMuted, fontSize: 11)),
    ]));
  }

  Widget _personal() => FutureBuilder<dynamic>(
    future: personal,
    builder: (context, snapshot) {
      // No spinner here: market baseline remains visible while this resolves.
      final items = fvRows(fvMap(snapshot.data)['items']);
      if (items.isEmpty) return const SizedBox.shrink();
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

  Widget _assets() => FutureBuilder<dynamic>(
      future: assets,
      builder: (context, snapshot) {
        final value = fvMap(snapshot.data);
        final cash = fvNumber(fvMap(value['cash'])['cash_balance']);
        final total = fvNumber(value['reference_total_asset_value']);
        return fvPanel(
            child: Row(children: [
          Expanded(
              child: Text(
                  '現金\n${cash == null ? '尚未設定' : '${legacy.accountingNumber(cash / 10000, decimals: 1)} 萬元'}')),
          Expanded(
              child: Text(
                  '參考總資產\n${total == null ? '資料尚未完整' : '${legacy.accountingNumber(total / 10000, decimals: 1)} 萬元'}')),
        ]));
      });

  Widget _liveHoldings() => FutureBuilder<dynamic>(
    future: ownerQuotes,
    builder: (context, snapshot) {
      final response = fvMap(snapshot.data ?? lastGoodOwnerQuotes);
      final positions = fvRows(response['positions']).map(fvMap)
          .where((row) => row['currency'] == 'TWD').take(3).toList();
      if (positions.isEmpty && snapshot.connectionState == ConnectionState.done
          && response.isEmpty) {
        return fvPanel(child: const Text('持股即時摘要暫時無法讀取；不使用舊報價冒充盤中資料',
            style: TextStyle(color: fvMuted)));
      }
      if (positions.isEmpty) return const SizedBox.shrink();
      final taipei = DateTime.now().toUtc().add(const Duration(hours: 8));
      final today = '${taipei.year.toString().padLeft(4, '0')}-'
          '${taipei.month.toString().padLeft(2, '0')}-'
          '${taipei.day.toString().padLeft(2, '0')}';
      return fvPanel(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('持股即時摘要', style: TextStyle(
              color: fvInk, fontSize: 19, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(marketHours ? '頁面可見時每分鐘更新 · 最多顯示 3 檔'
                           : '非盤中：保留最後有效行情，明確標示原始日期',
              style: const TextStyle(color: fvMuted, fontSize: 11)),
          for (final row in positions)
            Builder(builder: (context) {
              final symbol = fvText(row['symbol']);
              final quoteDate = fvText(row['price_date'], missing: '');
              final observedAt = DateTime.tryParse(fvText(row['quote_at'], missing: ''));
              final age = observedAt == null ? null : DateTime.now().difference(observedAt);
              final live = response['market_open'] == true &&
                  age != null && !age.isNegative && age.inSeconds <= 120 &&
                  row['quote_state'] == 'intraday' &&
                  row['price_status'] == 'available' &&
                  quoteDate == today &&
                  (row['price_source'] == 'shioaji' ||
                   row['price_source'] == 'twse_mis');
              final price = row['market_price'];
              final change = live ? row['change_percent'] : null;
              final pnl = live ? row['day_change_amount'] : null;
              final taipeiStamp = observedAt?.toUtc().add(const Duration(hours: 8));
              final quoteTime = taipeiStamp == null
                  ? '時間缺值'
                  : '${taipeiStamp.hour.toString().padLeft(2, '0')}:${taipeiStamp.minute.toString().padLeft(2, '0')}';
              return ListTile(
                key: Key('today-live-holding-$symbol'),
                dense: true,
                contentPadding: EdgeInsets.zero,
                selected: selectedHolding == symbol,
                title: Text('$symbol · ${fvText(row['stock_name'], missing: '持股')}',
                    maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: fvInk, fontWeight: FontWeight.w700)),
                subtitle: Text(live
                    ? '盤中 $quoteTime · 今日變化 ${pnl == null ? '缺值' : legacy.accountingNumber(pnl, decimals: 0)} 元'
                    : '非即時 · 價格日 ${quoteDate.isEmpty ? '缺值' : quoteDate}'),
                trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                  Column(mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.end, children: [
                    Text(price == null ? '—' : legacy.accountingNumber(price, decimals: 2),
                        style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
                    Text(change == null ? '—' : fvSignedPercent(change),
                        style: TextStyle(color: change == null ? fvMuted : fvSignedColor(change))),
                  ]),
                  IconButton(
                    tooltip: '開啟 $symbol 個股詳情',
                    icon: const Icon(Icons.chevron_right),
                    onPressed: () => widget.onOpenStock?.call(symbol),
                  ),
                ]),
                onTap: () => setState(() {
                  selectedHolding = symbol;
                  stockMinutes = _read(
                      '/api/v1/me/portfolio/intraday?symbol=$symbol');
                }),
              );
            }),
          if (selectedHolding != null) ...[
            const Divider(height: 14),
            Text('$selectedHolding · 今日觀測走勢',
                style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
            FutureBuilder<dynamic>(
              future: stockMinutes,
              builder: (context, state) {
                final data = fvMap(state.data);
                final points = fvRows(data['items']);
                if (points.length < 2) {
                  return fvBoundedState('已收集分鐘點不足，尚無法繪線；未開啟頁面時不會補抓歷史點');
                }
                return FvVisualSeriesChart(rows: points,
                    label: '$selectedHolding · 已收集分鐘點',
                    unit: '元／股', height: 170, intraday: true,
                    markExtrema: true, showTable: false);
              },
            ),
          ],
          const Text('資料來自 Shioaji／官方行情路由。日內變動與損益僅在可驗證的當日盤中報價下顯示。',
              style: TextStyle(color: fvMuted, fontSize: 11)),
        ],
      ));
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
        if (sections.isNotEmpty) ...[
          _marketActivityVisual(sections['market-activity']),
          _institutionalVisual(sections['institutional']),
        ],
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
      child: ListView(
        key: const Key('final-today-scroll'),
        padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
        children: [
          fvPageTitle(context, '今日', subtitle: '先看市場即時走勢與持股，再看其他資訊'),
          _assets(),
          _market(),
          _liveHoldings(),
          _personal(),
          _brief(),
          const Padding(
            padding: EdgeInsets.only(top: 12),
            child: Text('本服務提供研究資訊，不構成投資建議。',
                style: TextStyle(color: fvMuted, fontSize: 12)),
          ),
        ],
      ),
    ),
  );
}
