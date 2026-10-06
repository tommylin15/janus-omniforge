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
                value: (row.value / 100).clamp(0.0, 1.0),
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
  const FvKlineChart({required this.rows, super.key});

  final List<dynamic> rows;

  @override
  Widget build(BuildContext context) {
    final candles = <_Candle>[];
    for (final item in rows) {
      final row = fvMap(item);
      final day = DateTime.tryParse(fvText(row['trade_date'], missing: ''));
      final open = fvChartNumber(row['open']);
      final high = fvChartNumber(row['high']);
      final low = fvChartNumber(row['low']);
      final close = fvChartNumber(row['close']);
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
    final visible = candles.length > 40
        ? candles.sublist(candles.length - 40)
        : candles;
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
              const Expanded(
                child: Text(
                  'K 線／OHLCV',
                  style: TextStyle(
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
          const SizedBox(height: 10),
          SizedBox(
            height: hasVolume ? 240 : 195,
            width: double.infinity,
            child: CustomPaint(
              key: const Key('fv-kline-chart'),
              painter: _CandlestickPainter(visible, hasVolume: hasVolume),
            ),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              const _LegendDot(color: fvGain, label: '上漲'),
              const SizedBox(width: 14),
              const _LegendDot(color: fvLoss, label: '下跌'),
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
    final chartHeight = math.max(1.0, size.height - top - bottom);
    final values = points.map((item) => item.value).toList();
    var minValue = math.min(0.0, values.reduce(math.min));
    var maxValue = math.max(0.0, values.reduce(math.max));
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

    final width = math.max(1.0, size.width - left - right);
    final step = width / points.length;
    final barWidth = math.min(22.0, step * .56);
    for (var index = 0; index < points.length; index++) {
      final point = points[index];
      final x = left + step * (index + .5);
      final py = y(point.value);
      final rect = Rect.fromLTRB(
        x - barWidth / 2,
        math.min(py, baseline),
        x + barWidth / 2,
        math.max(py, baseline) + (point.value == 0 ? 1 : 0),
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

class _CandlestickPainter extends CustomPainter {
  _CandlestickPainter(this.candles, {required this.hasVolume});

  final List<_Candle> candles;
  final bool hasVolume;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 8.0;
    const right = 8.0;
    const top = 12.0;
    final volumeHeight = hasVolume ? 42.0 : 0.0;
    final bottom = hasVolume ? 64.0 : 30.0;
    final priceHeight = math.max(1.0, size.height - top - bottom);
    final lows = candles.map((item) => item.low).toList();
    final highs = candles.map((item) => item.high).toList();
    var minPrice = lows.reduce(math.min);
    var maxPrice = highs.reduce(math.max);
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
    final bodyWidth = math.min(9.0, math.max(3.0, step * .55));
    final maxVolume = hasVolume
        ? candles
            .map((item) => item.volume ?? 0)
            .fold<double>(0, math.max)
        : 0.0;
    final volumeTop = top + priceHeight + 16;

    for (var index = 0; index < candles.length; index++) {
      final candle = candles[index];
      final x = left + step * (index + .5);
      final color = candle.close >= candle.open ? fvGain : fvLoss;
      final wick = Paint()
        ..color = color
        ..strokeWidth = 1.4;
      canvas.drawLine(
        Offset(x, priceY(candle.high)),
        Offset(x, priceY(candle.low)),
        wick,
      );
      final openY = priceY(candle.open);
      final closeY = priceY(candle.close);
      final bodyTop = math.min(openY, closeY);
      final bodyBottom = math.max(openY, closeY);
      final rect = Rect.fromLTRB(
        x - bodyWidth / 2,
        bodyTop,
        x + bodyWidth / 2,
        math.max(bodyTop + 1.5, bodyBottom),
      );
      canvas.drawRect(rect, Paint()..color = color);

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
  bool shouldRepaint(covariant _CandlestickPainter oldDelegate) => true;
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
