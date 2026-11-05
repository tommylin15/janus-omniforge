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
  late Future<dynamic> marketFlows;
  late Future<dynamic> brief;
  late Future<dynamic> personal;
  late Future<dynamic> ownerQuotes;
  Future<dynamic>? stockMinutes;
  String? selectedHolding;
  bool showEtfs = false;
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
    marketFlows = widget.active
        ? _read('/api/v1/public/market-leverage-flow', timeout: const Duration(seconds: 28))
        : Future<dynamic>.value(null);
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
      marketFlows = widget.active
        ? _read('/api/v1/public/market-leverage-flow', timeout: const Duration(seconds: 28))
        : Future<dynamic>.value(null);
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
          marketFlows = _read('/api/v1/public/market-leverage-flow',
              timeout: const Duration(seconds: 28));
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
          // EOD margin / institutional data are refreshed on return to the
          // foreground, never on the 60-second intraday quote timer.
          marketFlows = _read('/api/v1/public/market-leverage-flow',
              timeout: const Duration(seconds: 28));
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
      // The default chart follows an ordinary share, not whichever ETF the
      // portfolio endpoint happens to return first.
      final ordinary = positions.where((row) => !_isEtf(row)).toList();
      if (selectedHolding == null ||
          !positions.any((row) => row['symbol'] == selectedHolding)) {
        selectedHolding = ordinary.isNotEmpty ? '${ordinary.first['symbol']}' : null;
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

  bool _isEtf(Map<String, dynamic> row) {
    final kind = fvText(row['instrument_kind'], missing: '').toUpperCase();
    return kind == 'ETF' || kind == 'BOND_ETF';
  }

  Widget _holdingCard(Map<String, dynamic> row, String today, Map<String, dynamic> response) {
    final symbol = fvText(row['symbol']);
    final name = fvText(row['stock_name'], missing: '持股');
    final quoteDate = fvText(row['price_date'], missing: '');
    final observedAt = DateTime.tryParse(fvText(row['quote_at'], missing: ''));
    final age = observedAt == null ? null : DateTime.now().difference(observedAt);
    final live = response['market_open'] == true &&
        age != null && !age.isNegative && age.inSeconds <= 120 &&
        row['quote_state'] == 'intraday' &&
        row['price_status'] == 'available' &&
        quoteDate == today &&
        (row['price_source'] == 'shioaji' || row['price_source'] == 'twse_mis');
    // A dated historical close can have a genuine previous-close delta.
    // Never call it today's move and never derive a missing comparison.
    final previousDate = fvText(row['previous_close_date'], missing: '');
    final hasHistoricalDelta = !live && quoteDate.isNotEmpty &&
        previousDate.isNotEmpty && previousDate.compareTo(quoteDate) < 0;
    final change = (live || hasHistoricalDelta) ? fvNumber(row['change']) : null;
    final percent = (live || hasHistoricalDelta) ? fvNumber(row['change_percent']) : null;
    final pnl = live ? fvNumber(row['day_change_amount']) : null;
    final taipeiStamp = observedAt?.toUtc().add(const Duration(hours: 8));
    final quoteTime = taipeiStamp == null ? '時間缺值' :
        '${taipeiStamp.hour.toString().padLeft(2, '0')}:${taipeiStamp.minute.toString().padLeft(2, '0')}';
    final color = change == null ? fvMuted : fvSignedColor(change);
    final selected = selectedHolding == symbol;
    return Material(
      color: selected ? fvSoft : Colors.white,
      borderRadius: BorderRadius.circular(13),
      child: InkWell(
        key: Key('today-live-holding-$symbol'),
        borderRadius: BorderRadius.circular(13),
        onTap: () => setState(() {
          selectedHolding = symbol;
          stockMinutes = _read('/api/v1/me/portfolio/intraday?symbol=$symbol');
        }),
        child: Container(
          height: 153,
          padding: const EdgeInsets.all(11),
          decoration: BoxDecoration(
            border: Border.all(color: selected ? fvTeal : const Color(0xFFE1E8EA),
                               width: selected ? 1.5 : 0.8),
            borderRadius: BorderRadius.circular(13),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(symbol, maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, color: fvMuted, fontWeight: FontWeight.w700))),
              const Icon(Icons.chevron_right, size: 17, color: fvMuted),
            ]),
            Text(name, maxLines: 1, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 15, color: fvInk, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text(row['market_price'] == null ? '—' :
                legacy.accountingNumber(row['market_price'], decimals: 2),
                maxLines: 1, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w800, color: fvInk)),
            if (change != null || percent != null)
              Row(children: [
                if (change != null) Flexible(child: Text(
                    '${change >= 0 ? '+' : ''}${legacy.accountingNumber(change, decimals: 2)}',
                    maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w700))),
                if (percent != null) ...[
                  const SizedBox(width: 5),
                  Flexible(child: Text(fvSignedPercent(percent), maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w700))),
                ],
              ])
            else const Text('漲跌尚無可比資料', style: TextStyle(fontSize: 10, color: fvMuted)),
            const Spacer(),
            Text(live ? '盤中 $quoteTime' :
                '非即時 · 價格日 ${quoteDate.isEmpty ? '缺值' : quoteDate}',
                maxLines: 1, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 10, color: fvMuted)),
            if (pnl != null)
              Text('當日持股變動 ${legacy.accountingNumber(pnl, decimals: 0)} 元',
                  maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 10, color: fvMuted)),
          ]),
        ),
      ),
    );
  }

  Widget _liveHoldings() => FutureBuilder<dynamic>(
    future: ownerQuotes,
    builder: (context, snapshot) {
      final response = fvMap(snapshot.data ?? lastGoodOwnerQuotes);
      final positions = fvRows(response['positions']).map(fvMap)
          .where((row) => row['currency'] == 'TWD' && row['symbol'] != null)
          .toList();
      if (positions.isEmpty && snapshot.connectionState == ConnectionState.done
          && response.isEmpty) {
        return fvPanel(child: const Text('持股行情暫時無法讀取；不使用舊報價冒充盤中資料',
            style: TextStyle(color: fvMuted)));
      }
      if (positions.isEmpty) return const SizedBox.shrink();
      final ordinary = positions.where((row) => !_isEtf(row)).toList();
      final etfs = positions.where(_isEtf).toList();
      final taipei = DateTime.now().toUtc().add(const Duration(hours: 8));
      final today = '${taipei.year.toString().padLeft(4, '0')}-'
          '${taipei.month.toString().padLeft(2, '0')}-'
          '${taipei.day.toString().padLeft(2, '0')}';
      Widget cards(List<Map<String, dynamic>> rows) => LayoutBuilder(
        builder: (context, bounds) {
          final columns = bounds.maxWidth < 330 ? 1 : 2;
          final width = (bounds.maxWidth - (columns - 1) * 10) / columns;
          return Wrap(spacing: 10, runSpacing: 10, children: [
            for (final row in rows)
              SizedBox(width: width, child: _holdingCard(row, today, response)),
          ]);
        },
      );
      return fvPanel(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('持股即時摘要', style: TextStyle(
              color: fvInk, fontSize: 19, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(marketHours ? '頁面可見時每分鐘更新 · 一般股票優先'
                           : '非盤中：保留最後有效行情，標示原始日期',
              style: const TextStyle(color: fvMuted, fontSize: 11)),
          const SizedBox(height: 10),
          Text('一般股票 · ${ordinary.length} 檔',
              style: const TextStyle(color: fvInk, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          if (ordinary.isEmpty)
            const Text('目前沒有一般股票持股', style: TextStyle(color: fvMuted))
          else cards(ordinary),
          if (etfs.isNotEmpty) ...[
            const SizedBox(height: 10),
            TextButton.icon(
              key: const Key('today-etf-toggle'),
              onPressed: () => setState(() { showEtfs = !showEtfs; }),
              icon: Icon(showEtfs ? Icons.expand_less : Icons.expand_more),
              label: Text('ETF／債券 ETF · ${etfs.length} 檔（${showEtfs ? '收合' : '展開'}）'),
            ),
            if (showEtfs) cards(etfs),
          ],
          if (selectedHolding != null) ...[
            const Divider(height: 18),
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
          const SizedBox(height: 6),
          const Text('Shioaji／官方行情路由；非盤中漲跌僅顯示可驗證的歷史收盤比較。',
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
          _leverageFlow(),
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
