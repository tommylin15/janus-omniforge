import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'main.dart' as legacy;

const fvGain = Color(0xFFD45252);
const fvLoss = Color(0xFF2E8B70);
const fvBlue = Color(0xFF2F6FB3);

double? fvChartNumber(Object? value) {
  if (value == null) return null;
  if (value is num) {
    final number = value.toDouble();
    return number.isFinite ? number : null;
  }
  var text = value.toString().replaceAll(',', '').trim();
  var negative = false;
  if (text.startsWith('(') && text.endsWith(')')) {
    negative = true;
    text = text.substring(1, text.length - 1);
  }
  final number = double.tryParse(text);
  if (number == null || !number.isFinite) return null;
  return negative ? -number : number;
}

class FvHealthBars extends StatelessWidget {
  const FvHealthBars({
    required this.dimensions,
    this.overall,
    super.key,
  });

  final Map<dynamic, dynamic> dimensions;
  final Object? overall;

  Color _scoreColor(double score) {
    if (score >= 75) return fvTeal;
    if (score >= 50) return fvBlue;
    return const Color(0xFFC47A28);
  }

  @override
  Widget build(BuildContext context) {
    final rows = <MapEntry<String, double>>[];
    for (final entry in dimensions.entries) {
      final score = fvChartNumber(entry.value);
      if (score != null) rows.add(MapEntry(entry.key.toString(), score));
    }
    return fvPanel(
      child: Column(
        key: const Key('fv-health-bars'),
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (overall != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                '整體健康度 ${legacy.accountingNumber(overall)}',
                style: const TextStyle(
                  color: fvInk,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          for (final row in rows) ...[
            Row(
              children: [
                Expanded(
                  child: Text(
                    legacy.uiLabel(row.key),
                    style: const TextStyle(
                      color: fvInk,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                Text(
                  legacy.accountingNumber(row.value),
                  style: TextStyle(
                    color: _scoreColor(row.value),
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                minHeight: 9,
                value: (row.value / 100).clamp(0.0, 1.0).toDouble(),
                backgroundColor: fvSoft,
                valueColor: AlwaysStoppedAnimation(_scoreColor(row.value)),
              ),
            ),
            const SizedBox(height: 11),
          ],
          if (rows.isEmpty && overall == null)
            const Text(
              '健康度分項尚無可視化資料',
              style: TextStyle(color: fvMuted),
            ),
        ],
      ),
    );
  }
}

class FvMonthlyPnlChart extends StatelessWidget {
  const FvMonthlyPnlChart({required this.rows, super.key});

  final List<dynamic> rows;

  @override
  Widget build(BuildContext context) {
    final points = <_MonthlyPnlPoint>[];
    for (final item in rows) {
      final row = fvMap(item);
      final month = fvInt(row['month']);
      final pnl = fvChartNumber(row['realized_pnl']);
      if (month >= 1 && month <= 12 && pnl != null) {
        points.add(_MonthlyPnlPoint(month, pnl));
      }
    }
    points.sort((a, b) => a.month.compareTo(b.month));
    if (points.isEmpty) {
      return fvBoundedState('月度已實現損益圖尚無可用資料');
    }
    return fvPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '月度已實現損益',
            style: TextStyle(
              color: fvInk,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            '直接呈現 Private Mart 月度 aggregate；不在手機端重算。',
            style: TextStyle(color: fvMuted, fontSize: 11),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 180,
            width: double.infinity,
            child: CustomPaint(
              key: const Key('fv-monthly-pnl-chart'),
              painter: _MonthlyPnlPainter(points),
            ),
          ),
          const SizedBox(height: 6),
          const Row(
            children: [
              _LegendDot(color: fvGain, label: '正損益'),
              SizedBox(width: 14),
              _LegendDot(color: fvLoss, label: '負損益'),
            ],
          ),
        ],
      ),
    );
  }
}

class FvKlineChart extends StatelessWidget {
  const FvKlineChart({
    required this.rows,
    this.maxPoints = 40,
    this.chartHeight,
    this.candlesticks = true,
    this.showKd = false,
    super.key,
  });

  final List<dynamic> rows;
  final int maxPoints;
  final double? chartHeight;
  final bool candlesticks;
  final bool showKd;

  @override
  Widget build(BuildContext context) {
    final candles = <_Candle>[];
    for (final item in rows) {
      final row = fvMap(item);
      final day = DateTime.tryParse(fvText(row['trade_date'], missing: ''));
      final close = fvChartNumber(row['close']);
      final open = candlesticks ? fvChartNumber(row['open']) : close;
      final high = candlesticks ? fvChartNumber(row['high']) : close;
      final low = candlesticks ? fvChartNumber(row['low']) : close;
      final volume = fvChartNumber(row['volume_shares']);
      if (day != null &&
          open != null &&
          high != null &&
          low != null &&
          close != null &&
          high >= low) {
        candles.add(_Candle(day, open, high, low, close, volume));
      }
    }
    candles.sort((a, b) => a.day.compareTo(b.day));
    final allKd = showKd ? _calculateKd(candles) : const <_KdPoint>[];
    final window = maxPoints.clamp(1, 264);
    final visible = candles.length > window
        ? candles.sublist(candles.length - window)
        : candles;
    final visibleKd = (showKd && allKd.length >= visible.length)
        ? allKd.sublist(allKd.length - visible.length)
        : const <_KdPoint>[];
    if (visible.isEmpty) return fvBoundedState('K 線資料不足，無法繪製');

    final hasVolume =
        visible.any((item) => item.volume != null && item.volume! > 0);
    final latest = visible.last;
    return fvPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  candlesticks ? 'K 線／OHLCV' : '收盤價／成交量',
                  style: const TextStyle(
                    color: fvInk,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Text(
                '近 ${visible.length} 日',
                style: const TextStyle(color: fvMuted, fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '最新 ${latest.day.toIso8601String().substring(0, 10)} · C ${legacy.accountingNumber(latest.close, decimals: 2)}',
            style: const TextStyle(color: fvMuted, fontSize: 11),
          ),
          const SizedBox(height: 5),
          const Text('顯示官方原始日價量，未進行除權息還原；不是含股利報酬。',
              style: TextStyle(color: fvMuted, fontSize: 11)),
          Text('價格：元／股 · 成交量：股 · 來源 ${rows.map(fvMap).map((r) => r['source_id']).whereType<String>().toSet().join('、')}',
            style: const TextStyle(color: fvMuted, fontSize: 11)),
          const SizedBox(height: 10),
          SizedBox(
            height: chartHeight ?? (hasVolume ? (showKd ? 295 : 240) : (showKd ? 250 : 195)),
            width: double.infinity,
            child: CustomPaint(
              key: const Key('fv-kline-chart'),
              painter: _CandlestickPainter(
                visible,
                hasVolume: hasVolume,
                candlesticks: candlesticks,
                showKd: showKd,
                kdPoints: visibleKd,
                gaps: rows.map(fvMap).where((row) => fvChartNumber(row['close']) == null)
                  .map((row) => DateTime.tryParse(fvText(row['trade_date'], missing: '')))
                  .whereType<DateTime>().toList(),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              const _LegendDot(color: fvGain, label: '上漲'),
              const SizedBox(width: 14),
              const _LegendDot(color: fvLoss, label: '下跌'),
              if (showKd && visibleKd.isNotEmpty) ...[
                const SizedBox(width: 14),
                const _LegendDot(color: Color(0xFFE65100), label: 'K(9,3)'),
                const SizedBox(width: 4),
                Text(visibleKd.last.k.toStringAsFixed(1), style: const TextStyle(color: Color(0xFFE65100), fontSize: 11, fontWeight: FontWeight.bold)),
                const SizedBox(width: 10),
                const _LegendDot(color: Color(0xFF1565C0), label: 'D(9,3)'),
                const SizedBox(width: 4),
                Text(visibleKd.last.d.toStringAsFixed(1), style: const TextStyle(color: Color(0xFF1565C0), fontSize: 11, fontWeight: FontWeight.bold)),
              ],
              if (!hasVolume) ...[
                const SizedBox(width: 14),
                const Expanded(
                  child: Text(
                    '成交量資料不足',
                    style: TextStyle(color: fvMuted, fontSize: 11),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 5),
          Text(label, style: const TextStyle(color: fvMuted, fontSize: 11)),
        ],
      );
}

class _MonthlyPnlPoint {
  const _MonthlyPnlPoint(this.month, this.value);
  final int month;
  final double value;
}

class _MonthlyPnlPainter extends CustomPainter {
  _MonthlyPnlPainter(this.points);

  final List<_MonthlyPnlPoint> points;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 8.0;
    const right = 8.0;
    const top = 10.0;
    const bottom = 28.0;
    final chartHeight = math.max(1.0, size.height - top - bottom).toDouble();
    final values = points.map((item) => item.value).toList();
    var minValue = math.min(0.0, values.reduce((a, b) => a < b ? a : b)).toDouble();
    var maxValue = math.max(0.0, values.reduce((a, b) => a > b ? a : b)).toDouble();
    if ((maxValue - minValue).abs() < 0.000001) {
      maxValue += 1;
      minValue -= 1;
    }
    final range = maxValue - minValue;
    double y(double value) => top + (maxValue - value) / range * chartHeight;
    final baseline = y(0);

    final gridPaint = Paint()
      ..color = fvSoft
      ..strokeWidth = 1;
    for (var index = 0; index < 3; index++) {
      final gy = top + chartHeight * index / 2;
      canvas.drawLine(Offset(left, gy), Offset(size.width - right, gy), gridPaint);
    }
    final axisPaint = Paint()
      ..color = fvMuted.withValues(alpha: .45)
      ..strokeWidth = 1;
    canvas.drawLine(
      Offset(left, baseline),
      Offset(size.width - right, baseline),
      axisPaint,
    );

    final width = math.max(1.0, size.width - left - right).toDouble();
    final step = width / points.length;
    final barWidth = math.min(22.0, step * .56).toDouble();
    for (var index = 0; index < points.length; index++) {
      final point = points[index];
      final x = left + step * (index + .5);
      final py = y(point.value);
      final rect = Rect.fromLTRB(
        x - barWidth / 2,
        py < baseline ? py : baseline,
        x + barWidth / 2,
        (py > baseline ? py : baseline) + (point.value == 0 ? 1 : 0),
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(4)),
        Paint()..color = point.value >= 0 ? fvGain : fvLoss,
      );
      _paintLabel(
        canvas,
        '${point.month}月',
        Offset(x, size.height - 16),
        center: true,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _MonthlyPnlPainter oldDelegate) => true;
}

class _Candle {
  const _Candle(
    this.day,
    this.open,
    this.high,
    this.low,
    this.close,
    this.volume,
  );

  final DateTime day;
  final double open;
  final double high;
  final double low;
  final double close;
  final double? volume;
}

class _KdPoint {
  const _KdPoint(this.k, this.d);
  final double k;
  final double d;
}

List<_KdPoint> _calculateKd(List<_Candle> candles) {
  if (candles.isEmpty) return const [];
  final points = <_KdPoint>[];
  var prevK = 50.0;
  var prevD = 50.0;

  for (var i = 0; i < candles.length; i++) {
    final start = math.max(0, i - 8);
    var minLow = candles[start].low;
    var maxHigh = candles[start].high;
    for (var j = start + 1; j <= i; j++) {
      if (candles[j].low < minLow) minLow = candles[j].low;
      if (candles[j].high > maxHigh) maxHigh = candles[j].high;
    }
    final rsv = (maxHigh - minLow).abs() < 1e-6
        ? 50.0
        : ((candles[i].close - minLow) / (maxHigh - minLow) * 100.0).clamp(0.0, 100.0);
    final k = (2.0 / 3.0) * prevK + (1.0 / 3.0) * rsv;
    final d = (2.0 / 3.0) * prevD + (1.0 / 3.0) * k;
    points.add(_KdPoint(k, d));
    prevK = k;
    prevD = d;
  }
  return points;
}

class _CandlestickPainter extends CustomPainter {
  _CandlestickPainter(
    this.candles, {
    required this.hasVolume,
    required this.candlesticks,
    required this.gaps,
    this.showKd = false,
    this.kdPoints = const [],
  });

  final List<_Candle> candles;
  final bool hasVolume;
  final bool candlesticks;
  final List<DateTime> gaps;
  final bool showKd;
  final List<_KdPoint> kdPoints;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 8.0;
    const right = 8.0;
    const top = 12.0;
    final volumeHeight = hasVolume ? 36.0 : 0.0;
    final kdHeight = showKd ? 45.0 : 0.0;
    final bottomMargin = 22.0;
    final subSectionGaps = (hasVolume ? 14.0 : 0.0) + (showKd ? 16.0 : 0.0);
    final priceHeight = math.max(60.0, size.height - top - bottomMargin - volumeHeight - kdHeight - subSectionGaps);
    final lows = candles.map((item) => item.low).toList();
    final highs = candles.map((item) => item.high).toList();
    var minPrice = lows.reduce((a, b) => a < b ? a : b);
    var maxPrice = highs.reduce((a, b) => a > b ? a : b);
    if ((maxPrice - minPrice).abs() < 0.000001) {
      maxPrice += 1;
      minPrice -= 1;
    }
    final priceRange = maxPrice - minPrice;
    double priceY(double value) =>
        top + (maxPrice - value) / priceRange * priceHeight;

    final gridPaint = Paint()
      ..color = fvSoft
      ..strokeWidth = 1;
    for (var index = 0; index < 4; index++) {
      final gy = top + priceHeight * index / 3;
      canvas.drawLine(Offset(left, gy), Offset(size.width - right, gy), gridPaint);
    }

    final width = math.max(1.0, size.width - left - right);
    final step = width / candles.length;
    final bodyWidth = math.min(9.0, math.max(3.0, step * .55)).toDouble();
    final maxVolume = hasVolume
        ? candles
            .map((item) => item.volume ?? 0)
            .fold<double>(0, (a, b) => a > b ? a : b)
        : 0.0;
    final volumeTop = top + priceHeight + 14.0;
    final volumeBottom = volumeTop + volumeHeight;
    final kdTop = hasVolume ? (volumeBottom + 16.0) : (top + priceHeight + 14.0);

    final line = Path();
    for (var index = 0; index < candles.length; index++) {
      final candle = candles[index];
      final x = left + step * (index + .5);
      final color = candle.close >= candle.open ? fvGain : fvLoss;
      final wick = Paint()
        ..color = color
        ..strokeWidth = 1.4;
      if (candlesticks) {
        canvas.drawLine(
          Offset(x, priceY(candle.high)),
          Offset(x, priceY(candle.low)),
          wick,
        );
        final openY = priceY(candle.open);
        final closeY = priceY(candle.close);
        final bodyTop = openY < closeY ? openY : closeY;
        final bodyBottom = openY > closeY ? openY : closeY;
        final rect = Rect.fromLTRB(
          x - bodyWidth / 2,
          bodyTop,
          x + bodyWidth / 2,
          bodyTop + 1.5 > bodyBottom ? bodyTop + 1.5 : bodyBottom,
        );
        canvas.drawRect(rect, Paint()..color = color);
      } else {
        final broken = index == 0 || gaps.any((day) => day.isAfter(candles[index - 1].day) && day.isBefore(candle.day));
        if (broken) { line.moveTo(x, priceY(candle.close)); }
        else { line.lineTo(x, priceY(candle.close)); }
      }

      if (hasVolume && maxVolume > 0 && candle.volume != null) {
        final h = volumeHeight * candle.volume! / maxVolume;
        canvas.drawRect(
          Rect.fromLTRB(
            x - bodyWidth / 2,
            volumeTop + volumeHeight - h,
            x + bodyWidth / 2,
            volumeTop + volumeHeight,
          ),
          Paint()..color = color.withValues(alpha: .45),
        );
      }
    }
    if (!candlesticks) {
      canvas.drawPath(line, Paint()..color = fvTeal..strokeWidth = 2.5..style = PaintingStyle.stroke);
    }

    if (showKd && kdPoints.length == candles.length) {
      double kdY(double val) => kdTop + (100.0 - val.clamp(0.0, 100.0)) / 100.0 * kdHeight;
      final refPaint = Paint()
        ..color = fvMuted.withValues(alpha: 0.25)
        ..strokeWidth = 0.8;
      canvas.drawLine(Offset(left, kdY(80)), Offset(size.width - right, kdY(80)), refPaint);
      canvas.drawLine(Offset(left, kdY(20)), Offset(size.width - right, kdY(20)), refPaint);
      _paintLabel(canvas, '80', Offset(left, kdY(80)), alignRight: false);
      _paintLabel(canvas, '20', Offset(left, kdY(20)), alignRight: false);

      final kPath = Path();
      final dPath = Path();
      for (var index = 0; index < candles.length; index++) {
        final x = left + step * (index + 0.5);
        final kd = kdPoints[index];
        final ky = kdY(kd.k);
        final dy = kdY(kd.d);
        if (index == 0) {
          kPath.moveTo(x, ky);
          dPath.moveTo(x, dy);
        } else {
          kPath.lineTo(x, ky);
          dPath.lineTo(x, dy);
        }
      }
      canvas.drawPath(kPath, Paint()..color = const Color(0xFFE65100)..strokeWidth = 1.6..style = PaintingStyle.stroke);
      canvas.drawPath(dPath, Paint()..color = const Color(0xFF1565C0)..strokeWidth = 1.6..style = PaintingStyle.stroke);
    }

    _paintLabel(
      canvas,
      candles.first.day.toIso8601String().substring(5, 10),
      Offset(left, size.height - 14),
    );
    _paintLabel(
      canvas,
      candles.last.day.toIso8601String().substring(5, 10),
      Offset(size.width - right, size.height - 14),
      alignRight: true,
    );
    _paintLabel(
      canvas,
      legacy.accountingNumber(maxPrice, decimals: 2),
      Offset(left, 2),
    );
    _paintLabel(
      canvas,
      legacy.accountingNumber(minPrice, decimals: 2),
      Offset(left, top + priceHeight - 12),
    );
  }

  @override
  bool shouldRepaint(covariant _CandlestickPainter oldDelegate) {
    if (candlesticks != oldDelegate.candlesticks || gaps.toString() != oldDelegate.gaps.toString() ||
        hasVolume != oldDelegate.hasVolume || candles.length != oldDelegate.candles.length ||
        showKd != oldDelegate.showKd || kdPoints.length != oldDelegate.kdPoints.length) {
      return true;
    }
    for (var i = 0; i < candles.length; i++) {
      final a = candles[i];
      final b = oldDelegate.candles[i];
      if (a.day != b.day || a.open != b.open || a.high != b.high ||
          a.low != b.low || a.close != b.close || a.volume != b.volume) {
        return true;
      }
    }
    return false;
  }
}

void _paintLabel(
  Canvas canvas,
  String text,
  Offset anchor, {
  bool center = false,
  bool alignRight = false,
}) {
  final painter = TextPainter(
    text: TextSpan(
      text: text,
      style: const TextStyle(color: fvMuted, fontSize: 9),
    ),
    textDirection: TextDirection.ltr,
  )..layout();
  var dx = anchor.dx;
  if (center) dx -= painter.width / 2;
  if (alignRight) dx -= painter.width;
  painter.paint(canvas, Offset(dx, anchor.dy - painter.height / 2));
}

class FvPeRiverChart extends StatefulWidget {
  const FvPeRiverChart({
    required this.klineRows,
    required this.epsRows,
    this.chartHeight = 280,
    super.key,
  });

  final List<dynamic> klineRows;
  final List<dynamic> epsRows;
  final double chartHeight;

  @override
  State<FvPeRiverChart> createState() => _FvPeRiverChartState();
}

class _FvPeRiverPoint {
  const _FvPeRiverPoint({
    required this.day,
    required this.close,
    required this.ttmEps,
    required this.pe,
    required this.bands,
  });
  final DateTime day;
  final double close;
  final double ttmEps;
  final double pe;
  final List<double> bands;
}

class _FvPeRiverChartState extends State<FvPeRiverChart> {
  int? highlightedIndex;

  @override
  Widget build(BuildContext context) {
    final epsPoints = <(DateTime, double)>[];
    for (final raw in widget.epsRows) {
      final map = fvMap(raw);
      final dt = DateTime.tryParse(fvText(map['date'] ?? map['fiscal_period_end'], missing: ''));
      final val = fvChartNumber(map['value'] ?? map['eps']);
      if (dt != null && val != null) {
        epsPoints.add((dt, val));
      }
    }
    epsPoints.sort((a, b) => a.$1.compareTo(b.$1));

    if (epsPoints.length < 4) {
      return fvPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('本益比估值河流圖 (P/E River)', style: TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            fvBoundedState('需要至少 4 季 EPS 才能計算近四季滾動 TTM EPS（目前僅有 ${epsPoints.length} 季）'),
          ],
        ),
      );
    }

    final dailyCandles = <(DateTime, double)>[];
    for (final raw in widget.klineRows) {
      final map = fvMap(raw);
      final dt = DateTime.tryParse(fvText(map['trade_date'], missing: ''));
      final close = fvChartNumber(map['close']);
      if (dt != null && close != null && close > 0) {
        dailyCandles.add((dt, close));
      }
    }
    dailyCandles.sort((a, b) => a.$1.compareTo(b.$1));

    if (dailyCandles.length < 2) {
      return fvPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('本益比估值河流圖 (P/E River)', style: TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            fvBoundedState('價格資料不足，無法繪製本益比河流圖'),
          ],
        ),
      );
    }

    final validPes = <double>[];
    final riverCandidates = <(DateTime, double, double, double)>[];
    for (final candle in dailyCandles) {
      final tDate = candle.$1;
      final close = candle.$2;
      final available = epsPoints.where((e) => e.$1.isBefore(tDate) || e.$1.isAtSameMomentAs(tDate)).toList();
      if (available.length >= 4) {
        final last4 = available.sublist(available.length - 4);
        final ttm = last4.fold<double>(0.0, (acc, item) => acc + item.$2);
        if (ttm > 0.05) {
          final pe = close / ttm;
          validPes.add(pe);
          riverCandidates.add((tDate, close, ttm, pe));
        }
      }
    }

    if (riverCandidates.length < 2 || validPes.isEmpty) {
      return fvPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('本益比估值河流圖 (P/E River)', style: TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            fvBoundedState('近四季 TTM EPS 均非正數（處於虧損或資料未銜接），本益比河流圖無法計算倍數'),
          ],
        ),
      );
    }

    validPes.sort();
    final p10 = validPes[(validPes.length * 0.1).floor().clamp(0, validPes.length - 1)];
    final p90 = validPes[(validPes.length * 0.9).floor().clamp(0, validPes.length - 1)];
    List<double> multiples;
    if (p90 <= 30.0 && p10 >= 10.0) {
      multiples = const [12.0, 16.0, 20.0, 24.0, 28.0];
    } else {
      final rawStep = (p90 - p10) / 4.0;
      final step = math.max(2.0, rawStep.roundToDouble());
      final base = math.max(step, ((p10 / step).round() * step));
      multiples = [base, base + step, base + 2 * step, base + 3 * step, base + 4 * step];
    }

    final riverPoints = <_FvPeRiverPoint>[];
    for (final cand in riverCandidates) {
      final bands = multiples.map((m) => m * cand.$3).toList();
      riverPoints.add(_FvPeRiverPoint(
        day: cand.$1,
        close: cand.$2,
        ttmEps: cand.$3,
        pe: cand.$4,
        bands: bands,
      ));
    }

    final curIdx = (highlightedIndex ?? (riverPoints.length - 1)).clamp(0, riverPoints.length - 1);
    final current = riverPoints[curIdx];

    String zoneLabel;
    Color zoneColor;
    if (current.close > current.bands[4]) {
      zoneLabel = '高於 ${multiples[4].toInt()}x · 昂貴區間';
      zoneColor = const Color(0xFFD45252);
    } else if (current.close > current.bands[3]) {
      zoneLabel = '${multiples[3].toInt()}x～${multiples[4].toInt()}x · 偏高區間';
      zoneColor = const Color(0xFFE65100);
    } else if (current.close > current.bands[1]) {
      zoneLabel = '${multiples[1].toInt()}x～${multiples[3].toInt()}x · 合理區間';
      zoneColor = const Color(0xFF2E8B70);
    } else if (current.close > current.bands[0]) {
      zoneLabel = '${multiples[0].toInt()}x～${multiples[1].toInt()}x · 偏低區間';
      zoneColor = const Color(0xFF1565C0);
    } else {
      zoneLabel = '低於 ${multiples[0].toInt()}x · 便宜區間';
      zoneColor = const Color(0xFF2F6FB3);
    }

    return fvPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  '本益比估值河流圖 (P/E River)',
                  style: TextStyle(
                    color: fvInk,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: zoneColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  zoneLabel,
                  style: TextStyle(
                    color: zoneColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '${current.day.toIso8601String().substring(0, 10)} · 收盤 ${legacy.accountingNumber(current.close, decimals: 2)} · TTM EPS ${current.ttmEps.toStringAsFixed(2)} 元 · 本益比 ${current.pe.toStringAsFixed(1)} 倍',
            style: const TextStyle(color: fvInk, fontSize: 12, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 3),
          Text(
            '河流倍數：${multiples.map((m) => '${m.toInt()}x').join('、')} · 近 ${riverPoints.length} 個交易日 · 輕觸圖表可滑動查看',
            style: const TextStyle(color: fvMuted, fontSize: 11),
          ),
          const SizedBox(height: 10),
          LayoutBuilder(
            builder: (context, constraints) => GestureDetector(
              onTapDown: (detail) {
                final ratio = ((detail.localPosition.dx - 8) / math.max(1, constraints.maxWidth - 16)).clamp(0.0, 1.0);
                setState(() => highlightedIndex = (ratio * (riverPoints.length - 1)).round());
              },
              onHorizontalDragUpdate: (detail) {
                final ratio = ((detail.localPosition.dx - 8) / math.max(1, constraints.maxWidth - 16)).clamp(0.0, 1.0);
                setState(() => highlightedIndex = (ratio * (riverPoints.length - 1)).round());
              },
              child: SizedBox(
                height: widget.chartHeight,
                width: double.infinity,
                child: CustomPaint(
                  key: const Key('fv-pe-river-chart'),
                  painter: _PeRiverPainter(
                    riverPoints,
                    highlightedIndex: curIdx,
                    multiples: multiples,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            children: [
              _LegendDot(color: const Color(0xFFEF5350).withValues(alpha: 0.7), label: '${multiples[3].toInt()}x～${multiples[4].toInt()}x 偏高'),
              _LegendDot(color: const Color(0xFFFFA726).withValues(alpha: 0.7), label: '${multiples[2].toInt()}x～${multiples[3].toInt()}x 中高'),
              _LegendDot(color: const Color(0xFF66BB6A).withValues(alpha: 0.7), label: '${multiples[1].toInt()}x～${multiples[2].toInt()}x 合理'),
              _LegendDot(color: const Color(0xFF29B6F6).withValues(alpha: 0.7), label: '${multiples[0].toInt()}x～${multiples[1].toInt()}x 偏低'),
              const _LegendDot(color: fvInk, label: '收盤價'),
            ],
          ),
        ],
      ),
    );
  }
}

class _PeRiverPainter extends CustomPainter {
  _PeRiverPainter(
    this.points, {
    required this.highlightedIndex,
    required this.multiples,
  });

  final List<_FvPeRiverPoint> points;
  final int highlightedIndex;
  final List<double> multiples;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;
    const left = 8.0;
    const right = 8.0;
    const top = 12.0;
    const bottom = 22.0;
    final chartHeight = math.max(1.0, size.height - top - bottom);
    final chartWidth = math.max(1.0, size.width - left - right);

    var minY = double.infinity;
    var maxY = double.negativeInfinity;
    for (final p in points) {
      if (p.close < minY) minY = p.close;
      if (p.close > maxY) maxY = p.close;
      for (final b in p.bands) {
        if (b < minY) minY = b;
        if (b > maxY) maxY = b;
      }
    }
    if ((maxY - minY).abs() < 1e-6) {
      maxY += 10.0;
      minY = math.max(0.0, minY - 10.0);
    } else {
      final pad = (maxY - minY) * 0.05;
      minY = math.max(0.0, minY - pad);
      maxY += pad;
    }
    final rangeY = maxY - minY;
    double y(double val) => top + (maxY - val) / rangeY * chartHeight;

    final gridPaint = Paint()
      ..color = fvSoft
      ..strokeWidth = 1;
    for (var i = 0; i < 4; i++) {
      final gy = top + chartHeight * i / 3.0;
      canvas.drawLine(Offset(left, gy), Offset(size.width - right, gy), gridPaint);
    }

    final step = chartWidth / (points.length - 1 == 0 ? 1 : points.length - 1);

    final zoneColors = [
      const Color(0xFF29B6F6).withValues(alpha: 0.22),
      const Color(0xFF66BB6A).withValues(alpha: 0.22),
      const Color(0xFFFFA726).withValues(alpha: 0.22),
      const Color(0xFFEF5350).withValues(alpha: 0.22),
    ];

    for (var b = 0; b < 4; b++) {
      final path = Path();
      for (var i = 0; i < points.length; i++) {
        final x = left + step * i;
        final py = y(points[i].bands[b + 1]);
        if (i == 0) {
          path.moveTo(x, py);
        } else {
          path.lineTo(x, py);
        }
      }
      for (var i = points.length - 1; i >= 0; i--) {
        final x = left + step * i;
        final py = y(points[i].bands[b]);
        path.lineTo(x, py);
      }
      path.close();
      canvas.drawPath(path, Paint()..color = zoneColors[b]..style = PaintingStyle.fill);
    }

    final bandLinePaint = Paint()
      ..color = const Color(0xFF90A4AE).withValues(alpha: 0.5)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;
    for (var b = 0; b < 5; b++) {
      final bPath = Path();
      for (var i = 0; i < points.length; i++) {
        final x = left + step * i;
        final py = y(points[i].bands[b]);
        if (i == 0) {
          bPath.moveTo(x, py);
        } else {
          bPath.lineTo(x, py);
        }
      }
      canvas.drawPath(bPath, bandLinePaint);
      final lastPy = y(points.last.bands[b]);
      _paintLabel(canvas, '${multiples[b].toInt()}x', Offset(size.width - right + 2, lastPy), alignRight: false);
    }

    final closePath = Path();
    for (var i = 0; i < points.length; i++) {
      final x = left + step * i;
      final py = y(points[i].close);
      if (i == 0) {
        closePath.moveTo(x, py);
      } else {
        closePath.lineTo(x, py);
      }
    }
    canvas.drawPath(
      closePath,
      Paint()
        ..color = fvInk
        ..strokeWidth = 2.4
        ..style = PaintingStyle.stroke,
    );

    final hIdx = highlightedIndex.clamp(0, points.length - 1);
    final hx = left + step * hIdx;
    final hy = y(points[hIdx].close);
    final cursorPaint = Paint()
      ..color = fvInk.withValues(alpha: 0.4)
      ..strokeWidth = 1.0;
    canvas.drawLine(Offset(hx, top), Offset(hx, top + chartHeight), cursorPaint);
    canvas.drawCircle(Offset(hx, hy), 4.5, Paint()..color = fvInk);
    canvas.drawCircle(Offset(hx, hy), 2.5, Paint()..color = Colors.white);

    _paintLabel(canvas, points.first.day.toIso8601String().substring(0, 10), Offset(left, size.height - 12));
    _paintLabel(canvas, points.last.day.toIso8601String().substring(0, 10), Offset(size.width - right, size.height - 12), alignRight: true);
    _paintLabel(canvas, legacy.accountingNumber(maxY, decimals: 1), Offset(left, 2));
    _paintLabel(canvas, legacy.accountingNumber(minY, decimals: 1), Offset(left, top + chartHeight - 12));
  }

  @override
  bool shouldRepaint(covariant _PeRiverPainter oldDelegate) => true;
}
