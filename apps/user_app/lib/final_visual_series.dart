import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'final_charts.dart';
import 'final_visual_common.dart';
import 'main.dart' as legacy;

/// UI-only published series; never fills gaps or computes a canonical value.
class FvVisualSeriesChart extends StatefulWidget {
  const FvVisualSeriesChart({required this.rows, required this.label, required this.unit,
    this.height = 175, super.key});
  final List<dynamic> rows;
  final String label;
  final String unit;
  final double height;
  @override
  State<FvVisualSeriesChart> createState() => _FvVisualSeriesChartState();
}

class _FvVisualSeriesChartState extends State<FvVisualSeriesChart> {
  int? highlighted;
  @override
  Widget build(BuildContext context) {
    final points = <(DateTime, double)>[];
    final seen = <String>{};
    for (final raw in widget.rows) {
      final item = fvMap(raw);
      final dateString = fvText(item['date'], missing: '');
      final day = DateTime.tryParse(dateString);
      final value = fvChartNumber(item['value']);
      if (day != null && value != null && value.isFinite && seen.add(dateString)) {
        points.add((day, value));
      }
    }
    points.sort((a, b) => a.$1.compareTo(b.$1));
    if (points.length < 2) return fvBoundedState('有效資料少於兩期，暫不繪製趨勢');
    final index = highlighted == null ? points.length - 1 :
      highlighted!.clamp(0, points.length - 1);
    final unit = widget.unit == 'times' ? '倍' : widget.unit == 'percent' ? '%' : widget.unit;
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text(widget.label, style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800))),
        Text('有效 ${points.length} 期', style: const TextStyle(color: fvMuted, fontSize: 11)),
      ]),
      const SizedBox(height: 5),
      Text('${points.first.$1.toIso8601String().substring(0, 10)} ～ ${points.last.$1.toIso8601String().substring(0, 10)} · $unit',
        style: const TextStyle(color: fvMuted, fontSize: 11)),
      const SizedBox(height: 10),
      LayoutBuilder(builder: (context, bounds) => GestureDetector(
        onTapDown: (detail) {
          final ratio = ((detail.localPosition.dx - 12) / math.max(1, bounds.maxWidth - 24))
            .clamp(0.0, 1.0);
          setState(() => highlighted = (ratio * (points.length - 1)).round());
        },
        child: Semantics(
          label: '${widget.label}，可點選歷史日期和數值',
          child: SizedBox(height: widget.height, width: double.infinity,
            child: CustomPaint(key: const Key('fv-visual-series-chart'),
              painter: _SeriesPainter(points, index))),
        ),
      )),
      const SizedBox(height: 8),
      Text('${points[index].$1.toIso8601String().substring(0, 10)}：${legacy.accountingNumber(points[index].$2, decimals: 2)} $unit',
        key: const Key('fv-series-tooltip'),
        style: const TextStyle(color: fvInk, fontSize: 12, fontWeight: FontWeight.w700)),
    ]));
  }
}

class _SeriesPainter extends CustomPainter {
  const _SeriesPainter(this.points, this.highlight);
  final List<(DateTime, double)> points;
  final int highlight;
  @override
  void paint(Canvas canvas, Size size) {
    final values = points.map((e) => e.$2);
    var low = values.reduce(math.min), high = values.reduce(math.max);
    if (low == high) { low -= 1; high += 1; }
    const pad = 12.0;
    final width = math.max(1.0, size.width - 2 * pad);
    final height = math.max(1.0, size.height - 2 * pad);
    Offset coord(int i) => Offset(pad + i * width / (points.length - 1),
      pad + (high - points[i].$2) * height / (high - low));
    final grid = Paint()..color = fvSoft..strokeWidth = 1;
    for (var i = 0; i < 3; i++) {
      final y = pad + height * i / 2;
      canvas.drawLine(Offset(pad, y), Offset(pad + width, y), grid);
    }
    final path = Path()..moveTo(coord(0).dx, coord(0).dy);
    for (var i = 1; i < points.length; i++) { path.lineTo(coord(i).dx, coord(i).dy); }
    canvas.drawPath(path, Paint()..color = fvTeal..strokeWidth = 2.5
      ..style = PaintingStyle.stroke..strokeCap = StrokeCap.round);
    canvas.drawCircle(coord(highlight), 4.5, Paint()..color = fvTeal);
    canvas.drawCircle(coord(highlight), 2, Paint()..color = Colors.white);
  }
  @override
  bool shouldRepaint(covariant _SeriesPainter old) => highlight != old.highlight ||
      points.length != old.points.length ||
      (points.isNotEmpty && old.points.isNotEmpty && points.last != old.points.last);
}
