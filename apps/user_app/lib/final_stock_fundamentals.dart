// 個股頁：週/月 K + 均線、月營收（單月/累計）＋股價、EPS＋股價。
// 只呈現已發布資料；缺值保留為缺口，不補值、不推算。
import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'final_charts.dart' show fvChartNumber;
import 'final_visual_common.dart';

const _maColors = <int, Color>{
  5: Color(0xFF8E24AA),
  20: Color(0xFFE65100),
  60: Color(0xFF1565C0),
  240: Color(0xFFD81B60),
};

class _Bar {
  _Bar(this.day, this.open, this.high, this.low, this.close, this.volume, this.ma);
  final DateTime day;
  final double open, high, low, close;
  final double? volume;
  final Map<int, double?> ma;
}

List<_Bar> _parseBars(List<dynamic> rows) {
  final bars = <_Bar>[];
  for (final item in rows) {
    final row = fvMap(item);
    final day = DateTime.tryParse(fvText(row['date'], missing: ''));
    final o = fvChartNumber(row['open']);
    final h = fvChartNumber(row['high']);
    final l = fvChartNumber(row['low']);
    final c = fvChartNumber(row['close']);
    if (day == null || o == null || h == null || l == null || c == null || h < l) continue;
    bars.add(_Bar(day, o, h, l, c, fvChartNumber(row['volume_shares']), {
      for (final w in _maColors.keys) w: fvChartNumber(row['ma$w']),
    }));
  }
  bars.sort((a, b) => a.day.compareTo(b.day));
  return bars;
}

/// 月底收盤（取 price-series period=month 的 bars），key = yyyy-mm。
Map<String, double> fvMonthlyCloseMap(List<dynamic> monthBars) {
  final out = <String, double>{};
  for (final bar in _parseBars(monthBars)) {
    out[_ym(bar.day)] = bar.close;
  }
  return out;
}

String _ym(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}';

List<({double k, double d})> _kd(List<_Bar> bars) {
  final out = <({double k, double d})>[];
  var k = 50.0, d = 50.0;
  for (var i = 0; i < bars.length; i++) {
    final from = math.max(0, i - 8);
    var hi = bars[from].high, lo = bars[from].low;
    for (var j = from; j <= i; j++) {
      hi = math.max(hi, bars[j].high);
      lo = math.min(lo, bars[j].low);
    }
    final rsv = hi == lo ? 50.0 : (bars[i].close - lo) / (hi - lo) * 100;
    k = k * 2 / 3 + rsv / 3;
    d = d * 2 / 3 + k / 3;
    out.add((k: k, d: d));
  }
  return out;
}

/// 日/週/月 K 線＋MA5/20/60/240＋成交量＋KD(9)。資料來自 /price-series。
class FvPeriodKChart extends StatelessWidget {
  const FvPeriodKChart({required this.payload, this.maxBars = 66, this.showKd = true, super.key});

  final Map<String, dynamic> payload;
  final int maxBars;
  final bool showKd;

  @override
  Widget build(BuildContext context) {
    final all = _parseBars(fvRows(payload['bars']));
    if (all.length < 2) {
      return fvBoundedState('K 線資料不足（${fvText(payload['missing_reason'], missing: '無已發布行情')}），不顯示示意圖');
    }
    final kdAll = _kd(all);
    final start = math.max(0, all.length - maxBars);
    final bars = all.sublist(start);
    final kd = kdAll.sublist(start);
    final last = bars.last;
    final prev = bars.length > 1 ? bars[bars.length - 2].close : null;
    final change = prev == null ? null : last.close - prev;
    final period = fvText(payload['period']);
    final unitLabel = const {'day': '日', 'week': '週', 'month': '月'}[period] ?? '';
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(
        '開 ${last.open.toStringAsFixed(2)} 高 ${last.high.toStringAsFixed(2)} 低 ${last.low.toStringAsFixed(2)} 收 ${last.close.toStringAsFixed(2)}'
        '${change == null ? '' : ' ${change >= 0 ? '▲' : '▼'}${change.abs().toStringAsFixed(2)} (${(change / prev! * 100).toStringAsFixed(2)}%)'}',
        style: TextStyle(color: change == null ? fvInk : fvSignedColor(change), fontSize: 12, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 4),
      Wrap(spacing: 10, children: [
        for (final entry in _maColors.entries)
          Text('${entry.key}MA ${last.ma[entry.key]?.toStringAsFixed(2) ?? '資料不足'}',
              style: TextStyle(color: entry.value, fontSize: 11, fontWeight: FontWeight.w700)),
      ]),
      const SizedBox(height: 6),
      SizedBox(
        height: showKd ? 340 : 260,
        width: double.infinity,
        child: CustomPaint(key: const Key('fv-period-k-chart'), painter: _PeriodKPainter(bars, showKd ? kd : const [])),
      ),
      const SizedBox(height: 4),
      Row(children: [
        Expanded(child: Text(
          '成交量 ${last.volume == null ? '—' : '${(last.volume! / 1000).toStringAsFixed(0)} 張'}'
          '${showKd ? ' · K(9) ${kd.last.k.toStringAsFixed(2)} D(9) ${kd.last.d.toStringAsFixed(2)}' : ''}',
          style: const TextStyle(color: fvMuted, fontSize: 11))),
      ]),
      Text('$unitLabel K · 官方原始價量，未還原除權息；均線不足期數時不畫。來源 ${fvRows(payload['source_ids']).join('、')}',
          style: const TextStyle(color: fvMuted, fontSize: 10)),
    ]));
  }
}

class _PeriodKPainter extends CustomPainter {
  _PeriodKPainter(this.bars, this.kd);
  final List<_Bar> bars;
  final List<({double k, double d})> kd;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 4.0, right = 44.0;
    final width = size.width - left - right;
    final hasKd = kd.length == bars.length && kd.isNotEmpty;
    final priceH = size.height * (hasKd ? .55 : .70);
    final volTop = priceH + 10;
    final volH = size.height * (hasKd ? .17 : .24);
    final kdTop = volTop + volH + 10;
    final kdH = size.height - kdTop - 12;
    var hi = bars.first.high, lo = bars.first.low;
    for (final b in bars) {
      hi = math.max(hi, b.high);
      lo = math.min(lo, b.low);
      for (final v in b.ma.values) {
        if (v != null) {
          hi = math.max(hi, v);
          lo = math.min(lo, v);
        }
      }
    }
    if (hi == lo) hi = lo + 1;
    final step = width / bars.length;
    final bodyW = math.max(1.0, step * .6);
    double y(double v) => 4 + (hi - v) / (hi - lo) * (priceH - 8);
    final grid = Paint()..color = fvMuted.withValues(alpha: .15);
    for (var i = 0; i <= 4; i++) {
      final v = lo + (hi - lo) * i / 4;
      canvas.drawLine(Offset(left, y(v)), Offset(left + width, y(v)), grid);
      _label(canvas, v.toStringAsFixed(v >= 100 ? 0 : 1), Offset(size.width - right + 3, y(v)));
    }
    final maxVol = bars.map((b) => b.volume ?? 0).fold<double>(0, math.max);
    for (var i = 0; i < bars.length; i++) {
      final b = bars[i];
      final x = left + step * (i + .5);
      final color = b.close > b.open ? fvGain : b.close < b.open ? fvLoss : fvMuted;
      final p = Paint()..color = color..strokeWidth = 1;
      canvas.drawLine(Offset(x, y(b.high)), Offset(x, y(b.low)), p);
      final top = math.min(y(b.open), y(b.close));
      final bottom = math.max(y(b.open), y(b.close));
      canvas.drawRect(Rect.fromLTRB(x - bodyW / 2, top, x + bodyW / 2, math.max(bottom, top + 1)), p);
      if (maxVol > 0 && b.volume != null) {
        final h = volH * b.volume! / maxVol;
        canvas.drawRect(Rect.fromLTRB(x - bodyW / 2, volTop + volH - h, x + bodyW / 2, volTop + volH),
            Paint()..color = color.withValues(alpha: .8));
      }
    }
    for (final entry in _maColors.entries) {
      final path = Path();
      var started = false;
      for (var i = 0; i < bars.length; i++) {
        final v = bars[i].ma[entry.key];
        if (v == null) {
          started = false;
          continue;
        }
        final pt = Offset(left + step * (i + .5), y(v));
        if (started) {
          path.lineTo(pt.dx, pt.dy);
        } else {
          path.moveTo(pt.dx, pt.dy);
          started = true;
        }
      }
      canvas.drawPath(path, Paint()..color = entry.value..strokeWidth = 1.3..style = PaintingStyle.stroke);
    }
    if (maxVol > 0) _label(canvas, '${(maxVol / 1000).toStringAsFixed(0)}張', Offset(size.width - right + 3, volTop + 4));
    if (hasKd) {
      double ky(double v) => kdTop + (100 - v.clamp(0, 100)) / 100 * kdH;
      for (final ref in const [20.0, 80.0]) {
        canvas.drawLine(Offset(left, ky(ref)), Offset(left + width, ky(ref)), grid);
        _label(canvas, ref.toStringAsFixed(0), Offset(size.width - right + 3, ky(ref)));
      }
      final kp = Path(), dp = Path();
      for (var i = 0; i < kd.length; i++) {
        final x = left + step * (i + .5);
        if (i == 0) {
          kp.moveTo(x, ky(kd[i].k));
          dp.moveTo(x, ky(kd[i].d));
        } else {
          kp.lineTo(x, ky(kd[i].k));
          dp.lineTo(x, ky(kd[i].d));
        }
      }
      canvas.drawPath(kp, Paint()..color = const Color(0xFF00897B)..strokeWidth = 1.4..style = PaintingStyle.stroke);
      canvas.drawPath(dp, Paint()..color = fvGain..strokeWidth = 1.4..style = PaintingStyle.stroke);
    }
    _label(canvas, bars.first.day.toIso8601String().substring(0, 10), Offset(left, size.height - 5));
    _label(canvas, bars.last.day.toIso8601String().substring(0, 10), Offset(left + width, size.height - 5), alignRight: true);
  }

  @override
  bool shouldRepaint(covariant _PeriodKPainter old) => old.bars != bars || old.kd != kd;
}

void _label(Canvas canvas, String text, Offset anchor, {bool alignRight = false, Color color = fvMuted}) {
  final tp = TextPainter(
    text: TextSpan(text: text, style: TextStyle(color: color, fontSize: 9)),
    textDirection: TextDirection.ltr,
  )..layout();
  tp.paint(canvas, Offset(alignRight ? anchor.dx - tp.width : anchor.dx, anchor.dy - tp.height / 2));
}

/// 柱狀（營收/EPS）＋股價折線，雙 Y 軸。
class _BarLinePainter extends CustomPainter {
  _BarLinePainter(this.labels, this.bars, this.line, this.barColor, this.lineColor);
  final List<String> labels;
  final List<double?> bars;
  final List<double?> line;
  final Color barColor, lineColor;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 40.0, right = 44.0, bottom = 16.0;
    final w = size.width - left - right;
    final h = size.height - bottom - 6;
    final vals = bars.whereType<double>();
    if (vals.isEmpty) return;
    final bMax = math.max(0.0, vals.reduce(math.max));
    final bMin = math.min(0.0, vals.reduce(math.min));
    final span = bMax - bMin == 0 ? 1.0 : bMax - bMin;
    double by(double v) => 6 + (bMax - v) / span * h;
    final grid = Paint()..color = fvMuted.withValues(alpha: .15);
    for (var i = 0; i <= 4; i++) {
      final v = bMin + span * i / 4;
      canvas.drawLine(Offset(left, by(v)), Offset(left + w, by(v)), grid);
      _label(canvas, v.toStringAsFixed(v.abs() >= 100 ? 0 : 2), Offset(left - 3, by(v)), alignRight: true);
    }
    final step = w / bars.length;
    for (var i = 0; i < bars.length; i++) {
      final v = bars[i];
      if (v == null) continue;
      final x = left + step * (i + .5);
      canvas.drawRect(Rect.fromLTRB(x - step * .35, math.min(by(v), by(0)), x + step * .35, math.max(by(v), by(0))),
          Paint()..color = barColor);
    }
    final lv = line.whereType<double>();
    if (lv.length >= 2) {
      final lMax = lv.reduce(math.max), lMin = lv.reduce(math.min);
      final ls = lMax - lMin == 0 ? 1.0 : lMax - lMin;
      double ly(double v) => 6 + (lMax - v) / ls * h;
      final path = Path();
      var started = false;
      for (var i = 0; i < line.length; i++) {
        final v = line[i];
        if (v == null) {
          started = false;
          continue;
        }
        final x = left + step * (i + .5);
        if (started) {
          path.lineTo(x, ly(v));
        } else {
          path.moveTo(x, ly(v));
          started = true;
        }
      }
      canvas.drawPath(path, Paint()..color = lineColor..strokeWidth = 1.4..style = PaintingStyle.stroke);
      for (var i = 0; i <= 4; i++) {
        final v = lMin + ls * i / 4;
        _label(canvas, v.toStringAsFixed(v >= 100 ? 0 : 1), Offset(left + w + 3, ly(v)), color: lineColor);
      }
    }
    String? lastYear;
    for (var i = 0; i < labels.length; i++) {
      final year = labels[i].substring(0, 4);
      if (year != lastYear) {
        _label(canvas, year, Offset(left + step * i, size.height - 6));
        lastYear = year;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _BarLinePainter old) => old.bars != bars || old.line != line;
}

Widget _legend(Color color, String label) => Row(mainAxisSize: MainAxisSize.min, children: [
      Container(width: 10, height: 10, color: color),
      const SizedBox(width: 4),
      Text(label, style: const TextStyle(fontSize: 11, color: fvInk)),
    ]);

Widget _pctCell(double? v) => Text(
      v == null ? '—' : '${v.toStringAsFixed(1)}%',
      textAlign: TextAlign.right,
      style: TextStyle(color: v == null ? fvMuted : fvSignedColor(v), fontSize: 12),
    );

Widget _cell(String text, {bool header = false, TextAlign align = TextAlign.right, Color? color}) => Text(text,
    textAlign: align,
    style: TextStyle(
        color: color ?? (header ? Colors.white : fvInk),
        fontSize: header ? 11 : 12,
        fontWeight: header ? FontWeight.w700 : FontWeight.w500));

Widget _table(List<String> header, List<List<Widget>> rows) => Table(
      columnWidths: const {0: FlexColumnWidth(1.1)},
      children: [
        TableRow(
          decoration: const BoxDecoration(color: Color(0xFF6F7C86)),
          children: [
            for (final h in header)
              Padding(padding: const EdgeInsets.symmetric(vertical: 7, horizontal: 4),
                  child: _cell(h, header: true, align: TextAlign.center)),
          ],
        ),
        for (var i = 0; i < rows.length; i++)
          TableRow(
            decoration: BoxDecoration(color: fvDatedRowColor(i)),
            children: [
              for (final c in rows[i]) Padding(padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4), child: c),
            ],
          ),
      ],
    );

/// 月營收：單月 / 累計月營收，柱狀＋月底股價，表格含年增率、月增率。
class FvRevenueChart extends StatefulWidget {
  const FvRevenueChart({required this.points, required this.monthlyClose, super.key});

  /// visual-series metric=revenue 的 points（單位：千元，date = 月底）。
  final List<dynamic> points;
  final Map<String, double> monthlyClose;

  @override
  State<FvRevenueChart> createState() => _FvRevenueChartState();
}

class _FvRevenueChartState extends State<FvRevenueChart> {
  bool cumulative = false;

  @override
  Widget build(BuildContext context) {
    // 千元 → 億元
    final monthly = <String, double>{};
    for (final p in widget.points) {
      final row = fvMap(p);
      final day = DateTime.tryParse(fvText(row['date'], missing: ''));
      final v = fvNumber(row['value']);
      if (day != null && v != null) monthly[_ym(day)] = v / 100000;
    }
    if (monthly.length < 2) return fvBoundedState('月營收資料不足，無法繪圖');
    final keys = monthly.keys.toList()..sort();
    // 累計：同年 1 月起連續加總；中間缺月則該年之後標示缺值，不推算。
    final cum = <String, double?>{};
    for (final k in keys) {
      final year = int.parse(k.substring(0, 4));
      final month = int.parse(k.substring(5));
      var total = 0.0;
      var complete = true;
      for (var m = 1; m <= month; m++) {
        final v = monthly['$year-${m.toString().padLeft(2, '0')}'];
        if (v == null) {
          complete = false;
          break;
        }
        total += v;
      }
      cum[k] = complete ? total : null;
    }
    double? series(String k) => cumulative ? cum[k] : monthly[k];
    String prevYear(String k) => '${int.parse(k.substring(0, 4)) - 1}${k.substring(4)}';
    String prevMonth(String k) {
      final y = int.parse(k.substring(0, 4)), m = int.parse(k.substring(5));
      return m == 1 ? '${y - 1}-12' : '$y-${(m - 1).toString().padLeft(2, '0')}';
    }

    double? growth(double? now, double? old) => now == null || old == null || old == 0 ? null : (now - old) / old.abs() * 100;
    final chartKeys = keys.length > 48 ? keys.sublist(keys.length - 48) : keys;
    final latestYear = keys.last.substring(0, 4);
    final lastYear = '${int.parse(latestYear) - 1}';
    final tableKeys = keys.where((k) => k.startsWith(latestYear)).toList().reversed.toList();
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: ChoiceChip(
            key: const Key('revenue-monthly'), label: const Center(child: Text('單月營收')),
            selected: !cumulative, onSelected: (_) => setState(() => cumulative = false))),
        const SizedBox(width: 8),
        Expanded(child: ChoiceChip(
            key: const Key('revenue-cumulative'), label: const Center(child: Text('累計月營收')),
            selected: cumulative, onSelected: (_) => setState(() => cumulative = true))),
      ]),
      const SizedBox(height: 8),
      Wrap(spacing: 14, children: [_legend(const Color(0xFF4FC3F7), '月營收（億元）'), _legend(const Color(0xFF8D4A1F), '股價（元）')]),
      SizedBox(
        height: 230,
        width: double.infinity,
        child: CustomPaint(painter: _BarLinePainter(
          chartKeys, [for (final k in chartKeys) series(k)], [for (final k in chartKeys) widget.monthlyClose[k]],
          const Color(0xFF4FC3F7), const Color(0xFF8D4A1F))),
      ),
      const SizedBox(height: 8),
      _table(
        ['月', '$latestYear年', '$lastYear年', '年增率(YOY)', if (!cumulative) '月增率(MOM)'],
        [
          for (final k in tableKeys)
            [
              _cell('${int.parse(k.substring(5))}', align: TextAlign.center),
              _cell(series(k)?.toStringAsFixed(2) ?? '—'),
              _cell(series(prevYear(k))?.toStringAsFixed(2) ?? '—'),
              _pctCell(growth(series(k), series(prevYear(k)))),
              if (!cumulative) _pctCell(growth(monthly[k], monthly[prevMonth(k)])),
            ],
        ],
      ),
      const SizedBox(height: 4),
      const Text('單位：億元。缺月不補值；累計值遇缺月顯示「—」。股價為月底收盤（未還原）。',
          style: TextStyle(color: fvMuted, fontSize: 10)),
    ]));
  }
}

/// EPS：單季 EPS 柱狀＋季底股價，表格含本益比（季底收盤 ÷ 近四季 EPS 合計）。
class FvEpsChart extends StatelessWidget {
  const FvEpsChart({required this.points, required this.monthlyClose, super.key});

  final List<dynamic> points;
  final Map<String, double> monthlyClose;

  @override
  Widget build(BuildContext context) {
    final eps = <String, double>{}; // key = yyyyQn
    for (final p in points) {
      final row = fvMap(p);
      final day = DateTime.tryParse(fvText(row['date'], missing: ''));
      final v = fvNumber(row['value']);
      if (day != null && v != null) eps['${day.year}Q${(day.month - 1) ~/ 3 + 1}'] = v;
    }
    if (eps.length < 2) return fvBoundedState('單季 EPS 資料不足，無法繪圖');
    final keys = eps.keys.toList()..sort();
    String prevQ(String k, int n) {
      var y = int.parse(k.substring(0, 4)), q = int.parse(k.substring(5));
      for (var i = 0; i < n; i++) {
        q -= 1;
        if (q == 0) {
          q = 4;
          y -= 1;
        }
      }
      return '${y}Q$q';
    }

    String quarterEndYm(String k) {
      final y = k.substring(0, 4), q = int.parse(k.substring(5));
      return '$y-${(q * 3).toString().padLeft(2, '0')}';
    }

    double? ttm(String k) {
      var sum = 0.0;
      for (var i = 0; i < 4; i++) {
        final v = eps[prevQ(k, i)];
        if (v == null) return null;
        sum += v;
      }
      return sum;
    }

    double? pe(String k) {
      final t = ttm(k);
      final price = monthlyClose[quarterEndYm(k)];
      return t == null || t <= 0 || price == null ? null : price / t;
    }

    final chartKeys = keys.length > 24 ? keys.sublist(keys.length - 24) : keys;
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Wrap(spacing: 14, children: [_legend(fvGain, 'EPS（元）'), _legend(const Color(0xFF546E7A), '股價（元）')]),
      SizedBox(
        height: 230,
        width: double.infinity,
        child: CustomPaint(painter: _BarLinePainter(
          chartKeys, [for (final k in chartKeys) eps[k]],
          [for (final k in chartKeys) monthlyClose[quarterEndYm(k)]], fvGain, const Color(0xFF546E7A))),
      ),
      const SizedBox(height: 8),
      _table(
        ['季度', 'EPS', '近四季EPS', '本益比'],
        [
          for (final k in keys.reversed.take(12))
            [
              _cell(k, align: TextAlign.center),
              _cell(eps[k]!.toStringAsFixed(2), color: fvSignedColor(eps[k])),
              _cell(ttm(k)?.toStringAsFixed(2) ?? '—'),
              _cell(pe(k)?.toStringAsFixed(1) ?? '—'),
            ],
        ],
      ),
      const SizedBox(height: 4),
      const Text('本益比 = 季底收盤 ÷ 近四季 EPS 合計；缺任一季或 EPS ≤ 0 時不計算。'
          '同業本益比、收益比、本業佔比、ROE、ROA 目前尚無已發布資料，暫不顯示。',
          style: TextStyle(color: fvMuted, fontSize: 10)),
    ]));
  }
}
