import 'dart:async';

import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'final_visual_series.dart';
import 'main.dart' as legacy;

/// Whether [now] falls within regular Taiwan stock market trading hours (Mon-Fri 09:00-13:30 Taipei).
bool taiexMarketHours(DateTime now) {
  final taipei = now.toUtc().add(const Duration(hours: 8));
  final minutes = taipei.hour * 60 + taipei.minute;
  return taipei.weekday <= 5 && minutes >= 540 && minutes < 810;
}

/// Returns true when [next] represents a newer or more authoritative index quote than [previous].
bool newerTaiexIndex(Map<String, dynamic> next, Map<String, dynamic> previous) {
  if (previous.isEmpty) return true;
  final nextDay = fvText(next['as_of'], missing: '');
  final priorDay = fvText(previous['as_of'], missing: '');
  if (nextDay != priorDay) return nextDay.compareTo(priorDay) > 0;
  final n = fvMap(next['data']);
  final p = fvMap(previous['data']);
  final previousFinal = previous['is_final'] == true ||
      (p['close'] != null && fvText(p['quote_state'], missing: '').isEmpty);
  if (previousFinal && next['is_final'] != true) return false;
  if (next['is_final'] == true && !previousFinal) return true;
  final nextAt = DateTime.tryParse(fvText(n['quote_at'], missing: ''));
  final priorAt = DateTime.tryParse(fvText(p['quote_at'], missing: ''));
  return nextAt != null && (priorAt == null || !nextAt.isBefore(priorAt));
}

/// Merges a fresher [next] index-quote section onto [base] while preserving dated history.
Map<String, dynamic> mergeTaiexIndexSummary(
  Map<String, dynamic> base,
  Map<String, dynamic>? next,
) {
  if (next == null || !newerTaiexIndex(next, base)) return base;
  return {
    ...base,
    ...next,
    'data': {...fvMap(base['data']), ...fvMap(next['data'])},
  };
}

/// Formats the TAIEX headline index value.
String taiexFormatValue(Map<String, dynamic> section) {
  final data = fvMap(section['data']);
  final value = data['close'] ?? data['index'] ?? data['value'];
  return value == null
      ? '資料尚未取得'
      : legacy.accountingNumber(value, decimals: 2);
}

/// Resolves the comparable previous close from an exchange tick or published Core history.
double? taiexSummaryPreviousClose(Map<String, dynamic> section) {
  final data = fvMap(section['data']);
  final date = fvText(section['as_of'], missing: '');
  final at = DateTime.tryParse(fvText(data['quote_at'], missing: ''));
  final state = fvText(data['quote_state'], missing: '');
  final quoteDay = at
      ?.toUtc()
      .add(const Duration(hours: 8))
      .toIso8601String()
      .substring(0, 10);
  final exchangeReference = fvNumber(data['quote_previous_close']);
  if (date.isNotEmpty &&
      quoteDay == date &&
      {'intraday', 'closing_pending_eod', 'stale'}.contains(state) &&
      exchangeReference != null &&
      exchangeReference.isFinite &&
      exchangeReference > 0) {
    return exchangeReference;
  }
  final tradeDate = DateTime.tryParse(date);
  if (tradeDate == null) return null;
  final candidates = fvRows(data['history_points'])
      .map(fvMap)
      .where((row) {
        final observedDate =
            DateTime.tryParse(fvText(row['date'], missing: ''));
        final close = fvNumber(row['value']);
        return observedDate != null &&
            observedDate.isBefore(tradeDate) &&
            tradeDate.difference(observedDate).inDays <= 7 &&
            close != null &&
            close.isFinite &&
            close > 0 &&
            fvText(row['source_id'], missing: '').isNotEmpty &&
            fvText(row['provenance_id'], missing: '').isNotEmpty;
      })
      .toList()
    ..sort((a, b) => fvText(b['date']).compareTo(fvText(a['date'])));
  return candidates.isEmpty ? null : fvNumber(candidates.first['value']);
}

/// Resolves previous close from intraday samples and official history for chart baselines.
double? taiexPreviousCloseFromHistory(
  List<dynamic> observed,
  List<dynamic> history,
  DateTime now,
) {
  final sampleDays = observed
      .map((raw) {
        final value = DateTime.tryParse(fvText(fvMap(raw)['date'], missing: ''));
        return value?.toUtc().add(const Duration(hours: 8));
      })
      .whereType<DateTime>()
      .toList()
    ..sort();
  final reference = sampleDays.isEmpty
      ? now.toUtc().add(const Duration(hours: 8))
      : sampleDays.last;
  final day = DateTime.utc(reference.year, reference.month, reference.day);
  final eligible = history
      .map(fvMap)
      .where((row) {
        final date = DateTime.tryParse(fvText(row['date'], missing: ''));
        final close = fvNumber(row['value']);
        return date != null &&
            date.isBefore(day) &&
            day.difference(date).inDays <= 7 &&
            close != null &&
            close.isFinite &&
            close > 0;
      })
      .toList()
    ..sort((a, b) => fvText(b['date']).compareTo(fvText(a['date'])));
  return eligible.isEmpty ? null : fvNumber(eligible.first['value']);
}

/// Formats the quote freshness caption shown under the TAIEX headline.
String taiexQuoteLabel(
  Map<String, dynamic> section,
  DateTime now,
  bool marketHours,
) {
  final data = fvMap(section['data']);
  final at = DateTime.tryParse(fvText(data['quote_at'], missing: ''));
  final state = fvText(data['quote_state'], missing: '');
  final date = fvText(section['as_of'], missing: '');
  final today = now.toUtc().add(const Duration(hours: 8));
  final tick = at?.toUtc().add(const Duration(hours: 8));
  final sameDay = tick != null &&
      tick.year == today.year &&
      tick.month == today.month &&
      tick.day == today.day;
  final age = at == null ? null : now.difference(at).inSeconds;
  if (marketHours &&
      state == 'intraday' &&
      sameDay &&
      age != null &&
      age >= 0 &&
      age <= 120) {
    return '盤中 ${tick.hour.toString().padLeft(2, '0')}:'
        '${tick.minute.toString().padLeft(2, '0')}:'
        '${tick.second.toString().padLeft(2, '0')}';
  }
  if (state.isNotEmpty) return '非即時 · ${date.isEmpty ? '日期缺值' : date}';
  return date.isNotEmpty ? '資料日 $date' : '行情日期缺值';
}

/// Shared compact TAIEX card presentation used on Today and Holdings pages.
class TaiexCompactCard extends StatelessWidget {
  const TaiexCompactCard({
    required this.snapshot,
    required this.lastGoodMarket,
    required this.indexSection,
    required this.indexBusy,
    required this.indexRefreshStatus,
    required this.marketHours,
    required this.now,
    required this.onRefreshIndex,
    this.onTapSummary,
    this.keyPrefix = 'today',
    super.key,
  });

  final AsyncSnapshot<dynamic> snapshot;
  final dynamic lastGoodMarket;
  final Map<String, dynamic>? indexSection;
  final bool indexBusy;
  final String? indexRefreshStatus;
  final bool marketHours;
  final DateTime now;
  final VoidCallback onRefreshIndex;
  final VoidCallback? onTapSummary;
  final String keyPrefix;

  Widget _refreshControls() {
    final status = indexBusy
        ? '更新中…'
        : indexRefreshStatus == 'unavailable' ||
                indexRefreshStatus == 'blocked'
            ? '行情暫未更新'
            : indexRefreshStatus == 'in_flight'
                ? '共用行情更新中'
                : indexRefreshStatus == 'throttled'
                    ? '更新節流 · 保留行情'
                    : marketHours
                        ? '每 15 秒檢查'
                        : '休市 · 手動更新';
    return Row(children: [
      Expanded(
        child: Text(
          status,
          key: Key('$keyPrefix-index-refresh-status'),
          style: const TextStyle(color: fvMuted, fontSize: 11),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      TextButton.icon(
        key: Key('$keyPrefix-index-refresh'),
        onPressed: indexBusy ? null : onRefreshIndex,
        style: TextButton.styleFrom(
          visualDensity: VisualDensity.compact,
          padding: const EdgeInsets.symmetric(horizontal: 8),
          foregroundColor: fvTeal,
        ),
        icon: indexBusy
            ? const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.refresh, size: 17),
        label: const Text('立即更新', style: TextStyle(fontSize: 12)),
      ),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final root = fvMap(snapshot.data ?? lastGoodMarket);
    final section = mergeTaiexIndexSummary(
      fvMap(fvMap(root['sections'])['taiex']),
      indexSection,
    );
    if (section.isEmpty) {
      return Column(children: [
        fvPanel(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Column(children: [
            const Row(children: [
              Text(
                '加權指數',
                style: TextStyle(
                  color: fvInk,
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                ),
              ),
              Spacer(),
              Text('行情尚未取得', style: TextStyle(color: fvMuted, fontSize: 14)),
            ]),
            _refreshControls(),
          ]),
        ),
        fvBoundedState(
          snapshot.connectionState == ConnectionState.done
              ? '大盤行情暫時無法取得'
              : '大盤資料仍在讀取；其他資訊可先使用',
        ),
      ]);
    }
    final data = fvMap(section['data']);
    final current = fvNumber(data['close'] ?? data['index'] ?? data['value']);
    final previous = taiexSummaryPreviousClose(section);
    final comparable = current != null &&
        current.isFinite &&
        current > 0 &&
        previous != null &&
        previous.isFinite &&
        previous > 0;
    final change = comparable ? current - previous : null;
    final ratio = comparable && change != null ? change / previous : null;
    final changeColor = change == null ? fvMuted : fvSignedColor(change);
    final points = change == null
        ? '—'
        : '${change > 0 ? '+' : change < 0 ? '-' : ''}'
            '${legacy.accountingNumber(change.abs(), decimals: 2)} 點';
    final percent = ratio == null ? '—' : fvSignedPercent(ratio);
    return fvPanel(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      child: Column(children: [
        InkWell(
          key: Key('$keyPrefix-market-summary'),
          onTap: onTapSummary,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(children: [
                const Text(
                  '加權指數',
                  style: TextStyle(
                    color: fvInk,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Align(
                    alignment: Alignment.centerRight,
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerRight,
                      child: Text(
                        taiexFormatValue(section),
                        key: Key('$keyPrefix-market-index-value'),
                        maxLines: 1,
                        softWrap: false,
                        style: const TextStyle(
                          color: fvInk,
                          fontSize: 24,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                const Icon(Icons.chevron_right, color: fvTeal),
              ]),
              const SizedBox(height: 3),
              Row(children: [
                Expanded(
                  child: Text(
                    taiexQuoteLabel(section, now, marketHours),
                    key: Key('$keyPrefix-market-quote-status'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: fvMuted, fontSize: 12),
                  ),
                ),
                const SizedBox(width: 6),
                if (comparable)
                  Flexible(
                    flex: 3,
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerRight,
                        child: Row(mainAxisSize: MainAxisSize.min, children: [
                          Text(
                            points,
                            key: Key('$keyPrefix-market-change-points'),
                            maxLines: 1,
                            softWrap: false,
                            style: TextStyle(
                              color: changeColor,
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            percent,
                            key: Key('$keyPrefix-market-change-percent'),
                            maxLines: 1,
                            softWrap: false,
                            style: TextStyle(
                              color: changeColor,
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ]),
                      ),
                    ),
                  )
                else
                  Text(
                    '漲跌待可比前收',
                    key: Key('$keyPrefix-market-change-unavailable'),
                    style: const TextStyle(color: fvMuted, fontSize: 13),
                  ),
              ]),
            ],
          ),
        ),
        const Divider(height: 8),
        _refreshControls(),
      ]),
    );
  }
}

/// Self-contained TAIEX card for non-Today pages (e.g. Holdings/Ledger).
class TaiexMarketCard extends StatefulWidget {
  const TaiexMarketCard({
    required this.api,
    this.active = true,
    this.clock = DateTime.now,
    this.keyPrefix = 'ledger',
    super.key,
  });

  final legacy.Api api;
  final bool active;
  final DateTime Function() clock;
  final String keyPrefix;

  @override
  State<TaiexMarketCard> createState() => _TaiexMarketCardState();
}

class _TaiexMarketCardState extends State<TaiexMarketCard>
    with WidgetsBindingObserver {
  late Future<dynamic> market;
  dynamic lastGoodMarket;
  Map<String, dynamic>? indexSection;
  bool indexBusy = false;
  String? indexRefreshStatus;
  int indexGeneration = 0;
  int marketGeneration = 0;
  bool marketBusy = false;
  bool foreground = true;
  Timer? marketTimer;
  Timer? indexTimer;

  static const _marketColdTimeout = Duration(seconds: 24);

  DateTime _now() => widget.clock();
  bool get _marketHours => taiexMarketHours(_now());
  bool get _marketActive =>
      widget.active && foreground && (ModalRoute.of(context)?.isCurrent ?? true);

  @override
  void initState() {
    super.initState();
    market = widget.active ? _loadMarket() : Future<dynamic>.value(null);
    WidgetsBinding.instance.addObserver(this);
    foreground = WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _startMarketTimer();
        _startIndexTimer();
      }
    });
  }

  Future<dynamic> _loadMarket() async {
    final generation = ++marketGeneration;
    marketBusy = true;
    try {
      final result = await widget.api
          .get('/api/v1/public/market-home')
          .timeout(_marketColdTimeout);
      if (mounted &&
          generation == marketGeneration &&
          result is Map &&
          result['sections'] is Map) {
        lastGoodMarket = result;
      }
      return result;
    } catch (_) {
      return null;
    } finally {
      if (generation == marketGeneration) marketBusy = false;
    }
  }

  void _startMarketTimer() {
    marketTimer?.cancel();
    if (_marketActive && _marketHours) {
      marketTimer = Timer.periodic(const Duration(minutes: 1), (_) {
        if (!_marketActive || !_marketHours) {
          marketTimer?.cancel();
        } else if (!marketBusy) {
          setState(() {
            market = _loadMarket();
          });
        }
      });
    }
  }

  void _startIndexTimer() {
    indexTimer?.cancel();
    if (!widget.active || !foreground) return;
    if (_marketActive && _marketHours) unawaited(_refreshIndex());
    indexTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      if (_marketActive && _marketHours) unawaited(_refreshIndex());
    });
  }

  Future<void> _refreshIndex({bool manual = false}) async {
    if (!mounted ||
        !_marketActive ||
        indexBusy ||
        (!manual && !_marketHours)) {
      return;
    }
    final generation = ++indexGeneration;
    final api = widget.api;
    setState(() => indexBusy = true);
    try {
      final path =
          '/api/v1/public/market-index-quote${manual ? '?force=true' : ''}';
      dynamic raw = await api.get(path).timeout(const Duration(seconds: 23));
      if (!mounted ||
          generation != indexGeneration ||
          !identical(api, widget.api)) {
        return;
      }
      if (manual && raw is Map && raw['refresh_status'] == 'in_flight') {
        await Future<void>.delayed(const Duration(seconds: 2));
        if (!mounted || generation != indexGeneration || !_marketActive) return;
        raw = await api
            .get('/api/v1/public/market-index-quote')
            .timeout(const Duration(seconds: 23));
      }
      if (!mounted ||
          generation != indexGeneration ||
          !identical(api, widget.api)) {
        return;
      }
      final response = fvMap(raw);
      final next = fvMap(response['section']);
      final nextData = fvMap(next['data']);
      final nextPrice = fvNumber(nextData['close']);
      final valid = response['schema_version'] == 'market-index-quote.v1' &&
          nextPrice != null &&
          nextPrice.isFinite &&
          nextPrice > 0 &&
          fvText(next['as_of'], missing: '').isNotEmpty;
      setState(() {
        if (valid && newerTaiexIndex(next, indexSection ?? {})) {
          indexSection = next;
        }
        indexRefreshStatus =
            response['schema_version'] == 'market-index-quote.v1'
                ? fvText(response['refresh_status'], missing: 'unavailable')
                : 'unavailable';
        if (!valid && indexRefreshStatus != 'in_flight') {
          indexRefreshStatus = 'unavailable';
        }
      });
    } catch (_) {
      if (mounted && generation == indexGeneration) {
        setState(() => indexRefreshStatus = 'unavailable');
      }
    } finally {
      if (mounted && generation == indexGeneration) {
        setState(() => indexBusy = false);
      }
    }
  }

  @override
  void didUpdateWidget(TaiexMarketCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.api, widget.api)) {
      lastGoodMarket = null;
      indexGeneration++;
      indexSection = null;
      indexBusy = false;
      indexRefreshStatus = null;
      _startIndexTimer();
      market = widget.active ? _loadMarket() : Future<dynamic>.value(null);
    }
    if (oldWidget.active != widget.active) {
      if (widget.active) {
        setState(() {
          market = _loadMarket();
        });
        _startMarketTimer();
        _startIndexTimer();
      } else {
        marketTimer?.cancel();
        indexTimer?.cancel();
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final resumed = state == AppLifecycleState.resumed;
    if (resumed == foreground) return;
    foreground = resumed;
    if (foreground && widget.active) {
      _startMarketTimer();
      _startIndexTimer();
    } else {
      marketTimer?.cancel();
      indexTimer?.cancel();
    }
  }

  @override
  void dispose() {
    marketTimer?.cancel();
    indexTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void _openDetailSheet() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => SafeArea(
        child: SizedBox(
          height: MediaQuery.sizeOf(sheetContext).height * 0.7,
          child: FutureBuilder<dynamic>(
            future: market,
            builder: (context, snapshot) {
              final root = fvMap(snapshot.data ?? lastGoodMarket);
              final section = mergeTaiexIndexSummary(
                fvMap(fvMap(root['sections'])['taiex']),
                indexSection,
              );
              final data = fvMap(section['data']);
              final history = fvRows(data['history_points']);
              final intraday = fvRows(data['intraday_points']);
              final previousClose =
                  taiexPreviousCloseFromHistory(intraday, history, _now());
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  const Text(
                    '加權指數 · 今日分鐘走勢',
                    style: TextStyle(
                      color: fvInk,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 10),
                  fvPanel(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '加權指數',
                          style: TextStyle(
                            color: fvInk,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          taiexFormatValue(section),
                          style: const TextStyle(
                            color: fvInk,
                            fontSize: 25,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          taiexQuoteLabel(section, _now(), _marketHours),
                          style: const TextStyle(color: fvMuted, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  FvIntradayProgressChart(
                    rows: intraday,
                    label: '加權指數 · 盤中',
                    unit: '點',
                    height: 190,
                    previousClose: previousClose,
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
        future: market,
        builder: (context, snapshot) => TaiexCompactCard(
          snapshot: snapshot,
          lastGoodMarket: lastGoodMarket,
          indexSection: indexSection,
          indexBusy: indexBusy,
          indexRefreshStatus: indexRefreshStatus,
          marketHours: _marketHours,
          now: _now(),
          keyPrefix: widget.keyPrefix,
          onRefreshIndex: () => unawaited(_refreshIndex(manual: true)),
          onTapSummary: _openDetailSheet,
        ),
      );
}
