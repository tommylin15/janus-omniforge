import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'final_charts.dart' show fvChartNumber;
import 'final_visual_common.dart';
import 'main.dart' as legacy;

/// Portfolio report: live allocation + true stored Mart valuations only.
/// Numbers calculated for selected slices are chart presentation sub-totals,
/// never a replacement for backend authoritative portfolio totals.
class FvPortfolioReport extends StatefulWidget {
  const FvPortfolioReport({required this.api, required this.snapshot, super.key});

  final legacy.Api api;
  final Map<String, dynamic> snapshot;

  @override
  State<FvPortfolioReport> createState() => _FvPortfolioReportState();
}

class _FvPortfolioReportState extends State<FvPortfolioReport> {
  int tab = 0;
  bool equities = true;
  bool etfs = true;
  bool allHistory = false;
  bool includeClosed = false;
  final Set<String> excluded = {};
  int? inspected;
  Future<dynamic>? history;

  Future<dynamic> _fetchHistory() => widget.api
      .get('/api/v1/me/portfolio/value-history?days=1825')
      .timeout(const Duration(seconds: 15));

  @override
  void didUpdateWidget(FvPortfolioReport oldWidget) {
    super.didUpdateWidget(oldWidget);
    final switchedOwner = oldWidget.api != widget.api;
    if (switchedOwner ||
        oldWidget.snapshot['checked_at'] != widget.snapshot['checked_at'] ||
        oldWidget.snapshot['ledger_version'] != widget.snapshot['ledger_version']) {
      history = tab == 1 ? _fetchHistory() : null;
      if (switchedOwner) {
        excluded.clear();
        equities = true;
        etfs = true;
        includeClosed = false;
        inspected = null;
      }
    }
  }

  static const palette = <Color>[
    Color(0xFF2DBEC4), Color(0xFFAD96D7), Color(0xFF55AEE3),
    Color(0xFFFFB481), Color(0xFFD57C81), Color(0xFF8A9CBC),
    Color(0xFFE1C51D), Color(0xFF90B356), Color(0xFF597B85),
    Color(0xFFC1A56A),
  ];

  String _name(Map<String, dynamic> row) =>
      fvText(row['stock_name'] ?? row['name'], missing:
          fvText(row['symbol'], missing: '未命名'));

  bool _etf(Map<String, dynamic> row) =>
      fvText(row['instrument_kind'], missing: '').toUpperCase().contains('ETF');

  bool _picked(Map<String, dynamic> row) {
    final symbol = fvText(row['symbol'], missing: '');
    if (excluded.contains(symbol)) return false;
    return _etf(row) ? etfs : equities;
  }

  List<Map<String, dynamic>> get positions =>
      fvRows(widget.snapshot['positions']).map(fvMap)
          .where((row) => row['currency'] == 'TWD' &&
              (fvChartNumber(row['shares']) ?? 0) > 0)
          .toList();

  String _amount(double value) => legacy.accountingNumber(value.round());

  Widget _selector() => SegmentedButton<int>(
        key: const Key('portfolio-report-tabs'),
        showSelectedIcon: false,
        style: SegmentedButton.styleFrom(
          selectedBackgroundColor: fvTeal,
          selectedForegroundColor: Colors.white,
          foregroundColor: fvInk,
        ),
        segments: const [
          ButtonSegment(value: 0, label: Text('持股市值占比')),
          ButtonSegment(value: 1, label: Text('持股市值走勢')),
        ],
        selected: {tab},
        onSelectionChanged: (values) => setState(() {
          tab = values.first;
          if (tab == 1) history ??= _fetchHistory();
          inspected = null;
        }),
      );

  Widget _filters({List<Map<String, dynamic>> historical = const []}) {
    final visible = <String, Map<String, dynamic>>{
      for (final row in positions) fvText(row['symbol']): row,
    };
    if (tab == 1 && includeClosed) {
      for (final row in historical) {
        final symbol = fvText(row['symbol'], missing: '');
        if (symbol.isNotEmpty) visible.putIfAbsent(symbol, () => row);
      }
    }
    return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(spacing: 8, runSpacing: 6, children: [
            FilterChip(
              key: const Key('portfolio-report-equities'),
              label: const Text('個股'),
              selected: equities,
              onSelected: (selected) => setState(() { equities = selected; inspected = null; }),
            ),
            FilterChip(
              key: const Key('portfolio-report-etfs'),
              label: const Text('ETF'),
              selected: etfs,
              onSelected: (selected) => setState(() { etfs = selected; inspected = null; }),
            ),
            if (tab == 1)
              FilterChip(
                key: const Key('portfolio-report-include-closed'),
                label: const Text('含已出清'),
                selected: includeClosed,
                onSelected: (selected) => setState(() {
                  includeClosed = selected;
                  inspected = null;
                }),
              ),
            TextButton(
              onPressed: () => setState(() { excluded.clear(); equities = true; etfs = true; inspected = null; }),
              child: const Text('全選'),
            ),
          ]),
          if (visible.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('選擇持股', style: TextStyle(color: fvMuted, fontSize: 12)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 7,
              runSpacing: 4,
              children: [
                for (final row in visible.values)
                  FilterChip(
                    key: Key('portfolio-report-symbol-${row['symbol']}'),
                    label: Text(_name(row)),
                    selected: !excluded.contains(fvText(row['symbol'])) && (_etf(row) ? etfs : equities),
                    onSelected: (selected) => setState(() {
                      final symbol = fvText(row['symbol']);
                      if (selected) {
                        excluded.remove(symbol);
                        if (_etf(row)) etfs = true; else equities = true;
                      } else {
                        excluded.add(symbol);
                      }
                      inspected = null;
                    }),
                  ),
              ],
            ),
          ],
        ],
      );
  }

  Widget _allocation() {
    final selected = <_Slice>[];
    final withoutPrices = <String>[];
    for (final row in positions) {
      if (!_picked(row)) continue;
      final value = fvChartNumber(row['market_value']);
      if (row['price_status'] != 'available' || value == null || value < 0) {
        withoutPrices.add(_name(row));
        continue;
      }
      if (value > 0) selected.add(_Slice(_name(row), fvText(row['symbol']), value));
    }
    selected.sort((a, b) => b.value.compareTo(a.value));
    final total = selected.fold<double>(0, (sum, item) => sum + item.value);
    final priceDates = positions.where(_picked)
        .where((row) => row['price_status'] == 'available')
        .map((row) => fvText(row['price_date'], missing: ''))
        .where((day) => RegExp(r'^\\d{4}-\\d{2}-\\d{2}
        positions.every((p) => p['price_status'] == 'available');
    final official = fvRows(widget.snapshot['items']).map(fvMap)
        .where((row) => row['currency'] == 'TWD' &&
            row['aggregate_status'] == 'available').toList();
    final officialValue = official.length == 1
        ? fvChartNumber(official.first['market_value']) : null;
    return Column(
      key: const Key('portfolio-allocation-view'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(allSelected && officialValue != null
            ? '持股總市值 TWD ${_amount(officialValue)}'
            : '所選已計價市值 TWD ${_amount(total)}',
          style: const TextStyle(color: fvInk, fontSize: 19, fontWeight: FontWeight.w800)),
        const SizedBox(height: 4),
        Text(priceDates.isEmpty
            ? '沒有可用報價日期 · 選股加總僅供比較，不包含現金'
            : '報價日 ${priceDates.join('／')} · 選股加總僅供比較，不包含現金',
          style: const TextStyle(color: fvMuted, fontSize: 11)),
        const SizedBox(height: 14),
        if (selected.isEmpty || total <= 0)
          fvBoundedState('沒有可繪製的持股市值；請選擇持股或檢查報價')
        else
          LayoutBuilder(builder: (context, constraints) {
            final narrow = constraints.maxWidth < 310;
            final pieSize = narrow ? math.min(220.0, constraints.maxWidth) :
                math.min(175.0, constraints.maxWidth * .46);
            final pie = SizedBox(
              width: pieSize, height: pieSize,
              child: Semantics(
                label: '所選持股市值圓餅圖，${selected.length} 檔',
                child: CustomPaint(
                  key: const Key('portfolio-allocation-pie'),
                  painter: _AllocationPainter(selected, total, palette),
                ),
              ),
            );
            final legend = Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < selected.length; i++)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 7),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Container(width: 10, height: 10,
                        margin: const EdgeInsets.only(top: 4, right: 7),
                        decoration: BoxDecoration(color: palette[i % palette.length],
                          borderRadius: BorderRadius.circular(3))),
                      Expanded(child: Text(
                        '${(selected[i].value / total * 100).toStringAsFixed(1)}%  ${selected[i].name}',
                        softWrap: true, style: const TextStyle(color: fvInk, fontSize: 12))),
                    ]),
                  ),
              ],
            );
            if (narrow) return Column(children: [pie, const SizedBox(height: 12), legend]);
            return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              pie, const SizedBox(width: 12), Expanded(child: legend),
            ]);
          }),
        if (withoutPrices.isNotEmpty) ...[
          const SizedBox(height: 12),
          fvBoundedState('未計價：${withoutPrices.join('、')}；缺價不以 0 填入'),
        ],
        const SizedBox(height: 18),
        _filters(),
      ],
    );
  }

  bool get _unfiltered => includeClosed && equities && etfs && excluded.isEmpty;

  List<_ValuePoint> _monthly(dynamic raw) {
    final result = fvMap(raw);
    final rows = fvRows(result['points']).map(fvMap).toList();
    final Map<String, bool> currentKinds = {
      for (final row in positions) fvText(row['symbol']): _etf(row),
    };
    final currentSymbols = currentKinds.keys.toSet();
    final Map<String, _ValuePoint> lastByMonth = {};
    for (final row in rows) {
      final date = DateTime.tryParse(fvText(row['date'], missing: ''));
      if (date == null) continue;
      double? market, cost;
      if (_unfiltered) {
        market = row['status'] == 'available'
            ? fvChartNumber(row['market_value']) : null;
        cost = fvChartNumber(row['cost_basis']);
      } else {
        market = 0;
        cost = 0;
        var partial = false;
        var incompleteCost = false;
        for (final item in fvRows(row['positions'])) {
          final holding = fvMap(item);
          final symbol = fvText(holding['symbol'], missing: '');
          if (!includeClosed && !currentSymbols.contains(symbol)) continue;
          final isEtf = currentKinds[symbol] ??
              fvText(holding['instrument_kind'], missing: '') == 'ETF';
          if (excluded.contains(symbol) || (isEtf ? !etfs : !equities)) continue;
          final value = fvChartNumber(holding['market_value']);
          final basis = fvChartNumber(holding['cost_basis']);
          if (basis == null) {
            incompleteCost = true;
          } else {
            cost = cost! + basis;
          }
          if (holding['status'] != 'available' || value == null) {
            partial = true;
          } else {
            market = market! + value;
          }
        }
        if (partial || incompleteCost) market = null;
        if (incompleteCost) cost = null;
      }
      final point = _ValuePoint(date, market, cost);
      final month = '${date.year}-${date.month.toString().padLeft(2, '0')}';
      // Use the latest *actual* snapshot of each month, never an interpolated point.
      lastByMonth[month] = point;
    }
    final points = lastByMonth.values.toList()..sort((a, b) => a.date.compareTo(b.date));
    final cutoff = DateTime.now().subtract(const Duration(days: 365));
    return allHistory ? points : points.where((p) => !p.date.isBefore(cutoff)).toList();
  }

  Widget _trend(dynamic historyData) {
    final result = fvMap(historyData);
    final points = _monthly(result);
    final historicalSymbols = <String, Map<String, dynamic>>{};
    for (final saved in fvRows(result['points'])) {
      for (final holding in fvRows(fvMap(saved)['positions'])) {
        final item = fvMap(holding);
        final symbol = fvText(item['symbol'], missing: '');
        if (symbol.isEmpty) continue;
        historicalSymbols[symbol] = <String, dynamic>{
          'symbol': symbol,
          'stock_name': fvText(item['name'], missing: symbol),
          'instrument_kind': fvText(item['instrument_kind'], missing: 'EQUITY'),
        };
      }
    }
    final valid = points.where((p) => p.market != null && p.cost != null).toList();
    final inspectedPoint = inspected != null && inspected! < points.length
        ? points[inspected!] : (points.isNotEmpty ? points.last : null);
    return Column(
      key: const Key('portfolio-value-trend-view'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('持股市值與投入成本的變化',
          style: TextStyle(color: fvInk, fontSize: 18, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
          ChoiceChip(label: const Text('近一年'), selected: !allHistory,
            onSelected: (_) => setState(() { allHistory = false; inspected = null; })),
          ChoiceChip(label: const Text('已存歷史（最多五年）'), selected: allHistory,
            onSelected: (_) => setState(() { allHistory = true; inspected = null; })),
        ]),
        const SizedBox(height: 6),
        const Text('每月取最後一筆實際估值；市值變動包含加碼、減碼與價格波動',
          style: TextStyle(color: fvMuted, fontSize: 11)),
        const SizedBox(height: 12),
        if (valid.length < 2)
          fvBoundedState('目前僅有 ${valid.length} 個可比月份；累積至少兩期正式估值後顯示走勢，不補造歷史價格')
        else ...[
          SizedBox(height: 236, width: double.infinity,
            child: LayoutBuilder(builder: (context, size) => GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTapDown: (tap) => setState(() {
                final width = math.max(1.0, size.maxWidth - 55);
                final fraction = ((tap.localPosition.dx - 47) / width).clamp(0.0, 1.0);
                final start = points.first.date.millisecondsSinceEpoch;
                final duration = points.last.date.millisecondsSinceEpoch - start;
                final target = start + fraction * duration;
                var closest = 0;
                for (var i = 1; i < points.length; i++) {
                  if ((points[i].date.millisecondsSinceEpoch - target).abs() <
                      (points[closest].date.millisecondsSinceEpoch - target).abs()) {
                    closest = i;
                  }
                }
                inspected = closest;
              }),
              child: CustomPaint(
                key: const Key('portfolio-value-trend-chart'),
                painter: _ValueTrendPainter(points, inspected),
              ),
            )),
          ),
          const SizedBox(height: 8),
          const Wrap(spacing: 18, runSpacing: 6, children: [
            _TrendLegend(color: Color(0xFF2DBEC4), label: '持股市值'),
            _TrendLegend(color: Color(0xFFFFAD78), label: '持有成本'),
          ]),
          if (inspectedPoint != null && inspectedPoint.market != null &&
              inspectedPoint.cost != null) ...[
            const SizedBox(height: 12),
            Text(
              '${inspectedPoint.date.year}/${inspectedPoint.date.month.toString().padLeft(2, '0')}  '
              '市值 ${_amount(inspectedPoint.market!)} · 成本 ${_amount(inspectedPoint.cost!)}',
              style: const TextStyle(color: fvInk, fontWeight: FontWeight.w700, fontSize: 12),
            ),
          ],
        ],
        if (result['truncated'] == true)
          fvBoundedState('歷史資料超過單次查詢上限，僅顯示已讀取部分'),
        if (result['status'] == 'partial')
          const Padding(padding: EdgeInsets.only(top: 8),
            child: Text('部分估值日缺少完整報價，圖上保留斷點',
              style: TextStyle(color: fvMuted, fontSize: 11))),
        const SizedBox(height: 18),
        _filters(historical: historicalSymbols.values.toList()),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _selector(),
          const SizedBox(height: 15),
          if (tab == 0)
            _allocation()
          else
            FutureBuilder<dynamic>(
              future: history,
              builder: (context, result) {
                if (result.connectionState != ConnectionState.done) {
                  return fvBoundedState('讀取已保存的歷史市值資料中');
                }
                if (result.hasError) return fvBoundedState('歷史估值讀取失敗，請重新整理');
                return _trend(result.data);
              },
            ),
        ],
      );
}

class _Slice {
  const _Slice(this.name, this.symbol, this.value);
  final String name;
  final String symbol;
  final double value;
}

class _AllocationPainter extends CustomPainter {
  const _AllocationPainter(this.slices, this.total, this.colors);
  final List<_Slice> slices;
  final double total;
  final List<Color> colors;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);
    var start = -math.pi / 2;
    for (var i = 0; i < slices.length; i++) {
      final sweep = 2 * math.pi * slices[i].value / total;
      canvas.drawArc(rect, start, sweep, true, Paint()..color = colors[i % colors.length]);
      start += sweep;
    }
  }

  @override
  bool shouldRepaint(covariant _AllocationPainter old) =>
      old.total != total || old.slices != slices;
}

class _ValuePoint {
  const _ValuePoint(this.date, this.market, this.cost);
  final DateTime date;
  final double? market;
  final double? cost;
}

class _TrendLegend extends StatelessWidget {
  const _TrendLegend({required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
    Container(width: 10, height: 10,
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
    const SizedBox(width: 5),
    Text(label, style: const TextStyle(color: fvMuted, fontSize: 12)),
  ]);
}

class _ValueTrendPainter extends CustomPainter {
  const _ValueTrendPainter(this.points, this.inspected);
  final List<_ValuePoint> points;
  final int? inspected;

  static const valueColor = Color(0xFF2DBEC4);
  static const costColor = Color(0xFFFFAD78);

  void _label(Canvas canvas, String label, Offset point,
      {Color color = fvMuted}) {
    final span = TextSpan(text: label, style: TextStyle(fontSize: 10, color: color));
    final tp = TextPainter(text: span, textDirection: TextDirection.ltr)..layout();
    tp.paint(canvas, point);
  }

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    const left = 47.0, right = 8.0, top = 13.0, bottom = 29.0;
    final height = size.height - top - bottom, width = size.width - left - right;
    if (height <= 0 || width <= 0) return;
    final values = <double>[];
    for (final point in points) {
      if (point.market != null) values.add(point.market!);
      if (point.cost != null) values.add(point.cost!);
    }
    if (values.isEmpty) return;
    var minValue = values.reduce(math.min);
    var maxValue = values.reduce(math.max);
    final delta = math.max(1.0, maxValue - minValue);
    minValue = math.max(0, minValue - delta * .10);
    maxValue += delta * .10;
    final span = math.max(1.0, maxValue - minValue);
    final first = points.first.date.millisecondsSinceEpoch.toDouble();
    final dateSpan = math.max(1.0,
        points.last.date.millisecondsSinceEpoch.toDouble() - first);
    double x(_ValuePoint p) => left +
        (p.date.millisecondsSinceEpoch - first) / dateSpan * width;
    double y(double value) => top + (maxValue - value) / span * height;
    for (var i = 0; i <= 4; i++) {
      final amount = minValue + (maxValue - minValue) * (4 - i) / 4;
      final gy = top + height * i / 4;
      canvas.drawLine(Offset(left, gy), Offset(size.width - right, gy),
          Paint()..color = fvSoft..strokeWidth = 1);
      _label(canvas, '${(amount / 10000).toStringAsFixed(0)}萬', Offset(0, gy - 7));
    }
    for (final point in [points.first, points[points.length ~/ 2], points.last]) {
      _label(canvas, '${point.date.year % 100}/${point.date.month}',
          Offset(x(point) - 13, size.height - 18));
    }
    void drawLine(double? Function(_ValuePoint) field, Color color) {
      Path path = Path();
      var active = false;
      DateTime? previous;
      for (final point in points) {
        final value = field(point);
        // A missing observation or an absent intervening month is a gap.
        if (value == null || previous != null &&
            point.date.difference(previous).inDays > 48) {
          if (active) canvas.drawPath(path, Paint()
            ..color = color..style = PaintingStyle.stroke
            ..strokeWidth = 2.5..strokeCap = StrokeCap.round);
          path = Path();
          active = false;
        }
        if (value != null) {
          if (!active) {
            path.moveTo(x(point), y(value));
            active = true;
          } else {
            path.lineTo(x(point), y(value));
          }
          canvas.drawCircle(Offset(x(point), y(value)), 2.5, Paint()..color = color);
        }
        previous = point.date;
      }
      if (active) canvas.drawPath(path, Paint()
        ..color = color..style = PaintingStyle.stroke
        ..strokeWidth = 2.5..strokeCap = StrokeCap.round);
    }
    drawLine((p) => p.market, valueColor);
    drawLine((p) => p.cost, costColor);
    if (inspected != null && inspected! >= 0 && inspected! < points.length) {
      final px = x(points[inspected!]);
      canvas.drawLine(Offset(px, top), Offset(px, size.height - bottom),
          Paint()..color = fvMuted..strokeWidth = .8);
    }
  }

  @override
  bool shouldRepaint(covariant _ValueTrendPainter old) =>
      old.points != points || old.inspected != inspected;
}
).hasMatch(day))
        .toSet().toList()..sort();
    final allSelected = equities && etfs && excluded.isEmpty &&
        positions.every((p) => p['price_status'] == 'available');
    final official = fvRows(widget.snapshot['items']).map(fvMap)
        .where((row) => row['currency'] == 'TWD' &&
            row['aggregate_status'] == 'available').toList();
    final officialValue = official.length == 1
        ? fvChartNumber(official.first['market_value']) : null;
    return Column(
      key: const Key('portfolio-allocation-view'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(allSelected && officialValue != null
            ? '持股總市值 TWD ${_amount(officialValue)}'
            : '所選已計價市值 TWD ${_amount(total)}',
          style: const TextStyle(color: fvInk, fontSize: 19, fontWeight: FontWeight.w800)),
        const SizedBox(height: 4),
        const Text('依最新已保存報價；選股加總僅供圖表比較，不包含現金',
          style: TextStyle(color: fvMuted, fontSize: 11)),
        const SizedBox(height: 14),
        if (selected.isEmpty || total <= 0)
          fvBoundedState('沒有可繪製的持股市值；請選擇持股或檢查報價')
        else
          LayoutBuilder(builder: (context, constraints) {
            final narrow = constraints.maxWidth < 310;
            final pieSize = narrow ? math.min(220.0, constraints.maxWidth) :
                math.min(175.0, constraints.maxWidth * .46);
            final pie = SizedBox(
              width: pieSize, height: pieSize,
              child: Semantics(
                label: '所選持股市值圓餅圖，${selected.length} 檔',
                child: CustomPaint(
                  key: const Key('portfolio-allocation-pie'),
                  painter: _AllocationPainter(selected, total, palette),
                ),
              ),
            );
            final legend = Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < selected.length; i++)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 7),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Container(width: 10, height: 10,
                        margin: const EdgeInsets.only(top: 4, right: 7),
                        decoration: BoxDecoration(color: palette[i % palette.length],
                          borderRadius: BorderRadius.circular(3))),
                      Expanded(child: Text(
                        '${(selected[i].value / total * 100).toStringAsFixed(1)}%  ${selected[i].name}',
                        softWrap: true, style: const TextStyle(color: fvInk, fontSize: 12))),
                    ]),
                  ),
              ],
            );
            if (narrow) return Column(children: [pie, const SizedBox(height: 12), legend]);
            return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              pie, const SizedBox(width: 12), Expanded(child: legend),
            ]);
          }),
        if (withoutPrices.isNotEmpty) ...[
          const SizedBox(height: 12),
          fvBoundedState('未計價：${withoutPrices.join('、')}；缺價不以 0 填入'),
        ],
        const SizedBox(height: 18),
        _filters(),
      ],
    );
  }

  bool get _unfiltered => includeClosed && equities && etfs && excluded.isEmpty;

  List<_ValuePoint> _monthly(dynamic raw) {
    final result = fvMap(raw);
    final rows = fvRows(result['points']).map(fvMap).toList();
    final Map<String, bool> currentKinds = {
      for (final row in positions) fvText(row['symbol']): _etf(row),
    };
    final currentSymbols = currentKinds.keys.toSet();
    final Map<String, _ValuePoint> lastByMonth = {};
    for (final row in rows) {
      final date = DateTime.tryParse(fvText(row['date'], missing: ''));
      if (date == null) continue;
      double? market, cost;
      if (_unfiltered) {
        market = row['status'] == 'available'
            ? fvChartNumber(row['market_value']) : null;
        cost = fvChartNumber(row['cost_basis']);
      } else {
        market = 0;
        cost = 0;
        var partial = false;
        var incompleteCost = false;
        for (final item in fvRows(row['positions'])) {
          final holding = fvMap(item);
          final symbol = fvText(holding['symbol'], missing: '');
          if (!includeClosed && !currentSymbols.contains(symbol)) continue;
          final isEtf = currentKinds[symbol] ??
              fvText(holding['instrument_kind'], missing: '') == 'ETF';
          if (excluded.contains(symbol) || (isEtf ? !etfs : !equities)) continue;
          final value = fvChartNumber(holding['market_value']);
          final basis = fvChartNumber(holding['cost_basis']);
          if (basis == null) {
            incompleteCost = true;
          } else {
            cost = cost! + basis;
          }
          if (holding['status'] != 'available' || value == null) {
            partial = true;
          } else {
            market = market! + value;
          }
        }
        if (partial || incompleteCost) market = null;
        if (incompleteCost) cost = null;
      }
      final point = _ValuePoint(date, market, cost);
      final month = '${date.year}-${date.month.toString().padLeft(2, '0')}';
      // Use the latest *actual* snapshot of each month, never an interpolated point.
      lastByMonth[month] = point;
    }
    final points = lastByMonth.values.toList()..sort((a, b) => a.date.compareTo(b.date));
    final cutoff = DateTime.now().subtract(const Duration(days: 365));
    return allHistory ? points : points.where((p) => !p.date.isBefore(cutoff)).toList();
  }

  Widget _trend(dynamic historyData) {
    final result = fvMap(historyData);
    final points = _monthly(result);
    final historicalSymbols = <String, Map<String, dynamic>>{};
    for (final saved in fvRows(result['points'])) {
      for (final holding in fvRows(fvMap(saved)['positions'])) {
        final item = fvMap(holding);
        final symbol = fvText(item['symbol'], missing: '');
        if (symbol.isEmpty) continue;
        historicalSymbols[symbol] = <String, dynamic>{
          'symbol': symbol,
          'stock_name': fvText(item['name'], missing: symbol),
          'instrument_kind': fvText(item['instrument_kind'], missing: 'EQUITY'),
        };
      }
    }
    final valid = points.where((p) => p.market != null && p.cost != null).toList();
    final inspectedPoint = inspected != null && inspected! < points.length
        ? points[inspected!] : (points.isNotEmpty ? points.last : null);
    return Column(
      key: const Key('portfolio-value-trend-view'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('持股市值與投入成本的變化',
          style: TextStyle(color: fvInk, fontSize: 18, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
          ChoiceChip(label: const Text('近一年'), selected: !allHistory,
            onSelected: (_) => setState(() { allHistory = false; inspected = null; })),
          ChoiceChip(label: const Text('已存歷史（最多五年）'), selected: allHistory,
            onSelected: (_) => setState(() { allHistory = true; inspected = null; })),
        ]),
        const SizedBox(height: 6),
        const Text('每月取最後一筆實際估值；市值變動包含加碼、減碼與價格波動',
          style: TextStyle(color: fvMuted, fontSize: 11)),
        const SizedBox(height: 12),
        if (valid.length < 2)
          fvBoundedState('目前僅有 ${valid.length} 個可比月份；累積至少兩期正式估值後顯示走勢，不補造歷史價格')
        else ...[
          SizedBox(height: 236, width: double.infinity,
            child: LayoutBuilder(builder: (context, size) => GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTapDown: (tap) => setState(() {
                final width = math.max(1.0, size.maxWidth - 55);
                final fraction = ((tap.localPosition.dx - 47) / width).clamp(0.0, 1.0);
                final start = points.first.date.millisecondsSinceEpoch;
                final duration = points.last.date.millisecondsSinceEpoch - start;
                final target = start + fraction * duration;
                var closest = 0;
                for (var i = 1; i < points.length; i++) {
                  if ((points[i].date.millisecondsSinceEpoch - target).abs() <
                      (points[closest].date.millisecondsSinceEpoch - target).abs()) {
                    closest = i;
                  }
                }
                inspected = closest;
              }),
              child: CustomPaint(
                key: const Key('portfolio-value-trend-chart'),
                painter: _ValueTrendPainter(points, inspected),
              ),
            )),
          ),
          const SizedBox(height: 8),
          const Wrap(spacing: 18, runSpacing: 6, children: [
            _TrendLegend(color: Color(0xFF2DBEC4), label: '持股市值'),
            _TrendLegend(color: Color(0xFFFFAD78), label: '持有成本'),
          ]),
          if (inspectedPoint != null && inspectedPoint.market != null &&
              inspectedPoint.cost != null) ...[
            const SizedBox(height: 12),
            Text(
              '${inspectedPoint.date.year}/${inspectedPoint.date.month.toString().padLeft(2, '0')}  '
              '市值 ${_amount(inspectedPoint.market!)} · 成本 ${_amount(inspectedPoint.cost!)}',
              style: const TextStyle(color: fvInk, fontWeight: FontWeight.w700, fontSize: 12),
            ),
          ],
        ],
        if (result['truncated'] == true)
          fvBoundedState('歷史資料超過單次查詢上限，僅顯示已讀取部分'),
        if (result['status'] == 'partial')
          const Padding(padding: EdgeInsets.only(top: 8),
            child: Text('部分估值日缺少完整報價，圖上保留斷點',
              style: TextStyle(color: fvMuted, fontSize: 11))),
        const SizedBox(height: 18),
        _filters(historical: historicalSymbols.values.toList()),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _selector(),
          const SizedBox(height: 15),
          if (tab == 0)
            _allocation()
          else
            FutureBuilder<dynamic>(
              future: history,
              builder: (context, result) {
                if (result.connectionState != ConnectionState.done) {
                  return fvBoundedState('讀取已保存的歷史市值資料中');
                }
                if (result.hasError) return fvBoundedState('歷史估值讀取失敗，請重新整理');
                return _trend(result.data);
              },
            ),
        ],
      );
}

class _Slice {
  const _Slice(this.name, this.symbol, this.value);
  final String name;
  final String symbol;
  final double value;
}

class _AllocationPainter extends CustomPainter {
  const _AllocationPainter(this.slices, this.total, this.colors);
  final List<_Slice> slices;
  final double total;
  final List<Color> colors;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);
    var start = -math.pi / 2;
    for (var i = 0; i < slices.length; i++) {
      final sweep = 2 * math.pi * slices[i].value / total;
      canvas.drawArc(rect, start, sweep, true, Paint()..color = colors[i % colors.length]);
      start += sweep;
    }
  }

  @override
  bool shouldRepaint(covariant _AllocationPainter old) =>
      old.total != total || old.slices != slices;
}

class _ValuePoint {
  const _ValuePoint(this.date, this.market, this.cost);
  final DateTime date;
  final double? market;
  final double? cost;
}

class _TrendLegend extends StatelessWidget {
  const _TrendLegend({required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
    Container(width: 10, height: 10,
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
    const SizedBox(width: 5),
    Text(label, style: const TextStyle(color: fvMuted, fontSize: 12)),
  ]);
}

class _ValueTrendPainter extends CustomPainter {
  const _ValueTrendPainter(this.points, this.inspected);
  final List<_ValuePoint> points;
  final int? inspected;

  static const valueColor = Color(0xFF2DBEC4);
  static const costColor = Color(0xFFFFAD78);

  void _label(Canvas canvas, String label, Offset point,
      {Color color = fvMuted}) {
    final span = TextSpan(text: label, style: TextStyle(fontSize: 10, color: color));
    final tp = TextPainter(text: span, textDirection: TextDirection.ltr)..layout();
    tp.paint(canvas, point);
  }

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    const left = 47.0, right = 8.0, top = 13.0, bottom = 29.0;
    final height = size.height - top - bottom, width = size.width - left - right;
    if (height <= 0 || width <= 0) return;
    final values = <double>[];
    for (final point in points) {
      if (point.market != null) values.add(point.market!);
      if (point.cost != null) values.add(point.cost!);
    }
    if (values.isEmpty) return;
    var minValue = values.reduce(math.min);
    var maxValue = values.reduce(math.max);
    final delta = math.max(1.0, maxValue - minValue);
    minValue = math.max(0, minValue - delta * .10);
    maxValue += delta * .10;
    final span = math.max(1.0, maxValue - minValue);
    final first = points.first.date.millisecondsSinceEpoch.toDouble();
    final dateSpan = math.max(1.0,
        points.last.date.millisecondsSinceEpoch.toDouble() - first);
    double x(_ValuePoint p) => left +
        (p.date.millisecondsSinceEpoch - first) / dateSpan * width;
    double y(double value) => top + (maxValue - value) / span * height;
    for (var i = 0; i <= 4; i++) {
      final amount = minValue + (maxValue - minValue) * (4 - i) / 4;
      final gy = top + height * i / 4;
      canvas.drawLine(Offset(left, gy), Offset(size.width - right, gy),
          Paint()..color = fvSoft..strokeWidth = 1);
      _label(canvas, '${(amount / 10000).toStringAsFixed(0)}萬', Offset(0, gy - 7));
    }
    for (final point in [points.first, points[points.length ~/ 2], points.last]) {
      _label(canvas, '${point.date.year % 100}/${point.date.month}',
          Offset(x(point) - 13, size.height - 18));
    }
    void drawLine(double? Function(_ValuePoint) field, Color color) {
      Path path = Path();
      var active = false;
      DateTime? previous;
      for (final point in points) {
        final value = field(point);
        // A missing observation or an absent intervening month is a gap.
        if (value == null || previous != null &&
            point.date.difference(previous).inDays > 48) {
          if (active) canvas.drawPath(path, Paint()
            ..color = color..style = PaintingStyle.stroke
            ..strokeWidth = 2.5..strokeCap = StrokeCap.round);
          path = Path();
          active = false;
        }
        if (value != null) {
          if (!active) {
            path.moveTo(x(point), y(value));
            active = true;
          } else {
            path.lineTo(x(point), y(value));
          }
          canvas.drawCircle(Offset(x(point), y(value)), 2.5, Paint()..color = color);
        }
        previous = point.date;
      }
      if (active) canvas.drawPath(path, Paint()
        ..color = color..style = PaintingStyle.stroke
        ..strokeWidth = 2.5..strokeCap = StrokeCap.round);
    }
    drawLine((p) => p.market, valueColor);
    drawLine((p) => p.cost, costColor);
    if (inspected != null && inspected! >= 0 && inspected! < points.length) {
      final px = x(points[inspected!]);
      canvas.drawLine(Offset(px, top), Offset(px, size.height - bottom),
          Paint()..color = fvMuted..strokeWidth = .8);
    }
  }

  @override
  bool shouldRepaint(covariant _ValueTrendPainter old) =>
      old.points != points || old.inspected != inspected;
}
