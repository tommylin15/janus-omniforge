import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'final_charts.dart' show fvChartNumber;
import 'final_visual_common.dart';
import 'main.dart' as legacy;

enum FvTableSummary { latest, sum, average }

/// UI-only published series; never fills gaps or computes a canonical value.
class FvVisualSeriesChart extends StatefulWidget {
  const FvVisualSeriesChart({required this.rows, required this.label, required this.unit,
    this.height = 175, this.bars = false, this.dailyTable = false,
    this.tableSummary = FvTableSummary.latest, super.key});
  final List<dynamic> rows;
  final String label;
  final String unit;
  final double height;
  final bool bars;
  final bool dailyTable;
  final FvTableSummary tableSummary;
  @override
  State<FvVisualSeriesChart> createState() => _FvVisualSeriesChartState();
}

class _FvVisualSeriesChartState extends State<FvVisualSeriesChart> {
  int? highlighted;
  @override
  Widget build(BuildContext context) {
    // Preserve explicitly missing dates as breaks; never interpolate a gap.
    final samples = <(DateTime, double?)>[];
    final seen = <String>{};
    for (final raw in widget.rows) {
      final item = fvMap(raw);
      final dateString = fvText(item['date'], missing: '');
      final day = DateTime.tryParse(dateString);
      if (day != null && seen.add(dateString)) {
        samples.add((day, fvChartNumber(item['value'])));
      }
    }
    samples.sort((a, b) => a.$1.compareTo(b.$1));
    final points = <(DateTime, double)>[];
    final breakBefore = <int>{};
    var missingBetween = false;
    for (final sample in samples) {
      if (sample.$2 == null) {
        missingBetween = true;
        continue;
      }
      if (missingBetween && points.isNotEmpty) breakBefore.add(points.length);
      points.add((sample.$1, sample.$2!));
      missingBetween = false;
    }
    if (points.length < 2) return fvBoundedState('有效資料少於兩期，暫不繪製趨勢');
    final index = highlighted == null ? points.length - 1 :
      highlighted!.clamp(0, points.length - 1);
    final unit = const {'times': '倍', 'percent': '%', 'shares': '股',
      'TWD_thousands': '千元', 'TWD_per_share': '元／股'}[widget.unit] ?? widget.unit;
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text(widget.label, style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800))),
        Text('有效 ${points.length} 期', style: const TextStyle(color: fvMuted, fontSize: 11)),
      ]),
      const SizedBox(height: 5),
      Text('${points.first.$1.toIso8601String().substring(0, 10)} ～ ${points.last.$1.toIso8601String().substring(0, 10)} · $unit',
        style: const TextStyle(color: fvMuted, fontSize: 11)),
      if (samples.any((sample) => sample.$2 == null))
        const Text('部分日期缺值，圖線不跨越缺口',
          style: TextStyle(color: fvMuted, fontSize: 11)),
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
              painter: _SeriesPainter(points, index, breakBefore, widget.bars))),
        ),
      )),
      const SizedBox(height: 8),
      Text('${points[index].$1.toIso8601String().substring(0, 10)}：${legacy.accountingNumber(points[index].$2, decimals: 2)} $unit',
        key: const Key('fv-series-tooltip'),
        style: const TextStyle(color: fvInk, fontSize: 12, fontWeight: FontWeight.w700)),
      _SeriesTable(samples: samples, unit: unit, daily: widget.dailyTable,
          summary: widget.tableSummary),
    ]));
  }
}

class _SeriesTable extends StatelessWidget {
  const _SeriesTable({required this.samples, required this.unit,
      required this.daily, required this.summary});
  final List<(DateTime, double?)> samples;
  final String unit;
  final bool daily;
  final FvTableSummary summary;

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final cutoff = DateTime(now.year - 2, now.month, now.day);
    final recent = daily ? samples.reversed :
        samples.reversed.where((point) => !point.$1.isBefore(cutoff));
    final rows = (daily ? recent.take(20) : recent).toList();
    final quarters = <String, List<(DateTime, double?)>>{};
    for (final row in rows) {
      final key = '${row.$1.year} Q${(row.$1.month - 1) ~/ 3 + 1}';
      quarters.putIfAbsent(key, () => []).add(row);
    }
    return ExpansionTile(title: const Text('圖表資料'),
      subtitle: Text(daily ? '最新在上 · 最近20期日資料' : '最新在上 · 近兩年'),
      children: [
        if (rows.isEmpty) const ListTile(title: Text('近兩年沒有已發布資料')),
        for (final quarter in quarters.entries)
          ExpansionTile(
            key: ValueKey('series-quarter-${quarter.key}'),
            backgroundColor: fvCanvas,
            collapsedBackgroundColor: fvCanvas,
            title: Text(quarter.key),
            subtitle: Text(_summary(quarter.value)),
            children: [
              for (final (index, point) in quarter.value.indexed)
                Material(color: fvDatedRowColor(index), child: ListTile(
                  key: ValueKey('series-table-row-${point.$1.toIso8601String().substring(0, 10)}'),
                  dense: true,
                  title: Text(point.$1.toIso8601String().substring(0, 10)),
                  trailing: Text('${legacy.accountingNumber(point.$2, decimals: 2, missing: '缺值')} $unit'))),
            ],
          ),
        if (summary != FvTableSummary.latest && rows.isNotEmpty)
          const Padding(padding: EdgeInsets.all(8), child: Text(
            '僅彙總表列有效觀測，不代表完整季度報表；不補缺值。',
            style: TextStyle(color: fvMuted, fontSize: 11))),
      ]);
  }

  String _summary(List<(DateTime, double?)> rows) {
    final count = '${rows.length} 期';
    if (rows.any((row) => row.$2 == null)) return '$count · 含缺值，不彙總';
    final values = rows.map((row) => row.$2!);
    final value = switch (summary) {
      FvTableSummary.latest => values.first,
      FvTableSummary.sum => values.reduce((a, b) => a + b),
      FvTableSummary.average => values.reduce((a, b) => a + b) / rows.length,
    };
    final label = switch (summary) {
      FvTableSummary.latest => '最新',
      FvTableSummary.sum => '表列合計',
      FvTableSummary.average => '表列平均',
    };
    return '$count · $label ${legacy.accountingNumber(value, decimals: 2)} $unit';
  }
}

class _SeriesPainter extends CustomPainter {
  const _SeriesPainter(this.points, this.highlight, this.breakBefore, this.bars);
  final List<(DateTime, double)> points;
  final int highlight;
  final Set<int> breakBefore;
  final bool bars;
  @override
  void paint(Canvas canvas, Size size) {
    final values = points.map((e) => e.$2);
    var low = values.reduce(math.min), high = values.reduce(math.max);
    if (bars) { low = math.min(0, low); high = math.max(0, high); }
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
    for (final entry in [(high, pad), (low, pad + height)]) {
      final label = TextPainter(text: TextSpan(text: legacy.accountingNumber(entry.$1, decimals: 2),
        style: const TextStyle(fontSize: 10, color: fvMuted)), textDirection: TextDirection.ltr)..layout();
      label.paint(canvas, Offset(pad, entry.$2.clamp(0, size.height - label.height)));
    }
    if (bars) {
      final zeroY = pad + high * height / (high - low);
      canvas.drawLine(Offset(pad, zeroY), Offset(pad + width, zeroY), Paint()..color = fvMuted);
      final barWidth = math.min(20.0, width / points.length * .65);
      for (var i = 0; i < points.length; i++) {
        final position = coord(i);
        canvas.drawRect(Rect.fromLTRB(position.dx - barWidth / 2, math.min(position.dy, zeroY),
          position.dx + barWidth / 2, math.max(position.dy, zeroY)),
          Paint()..color = points[i].$2 < 0 ? fvLoss : fvGain);
      }
      return;
    }
    final path = Path()..moveTo(coord(0).dx, coord(0).dy);
    for (var i = 1; i < points.length; i++) {
      if (breakBefore.contains(i)) {
        path.moveTo(coord(i).dx, coord(i).dy);
      } else {
        path.lineTo(coord(i).dx, coord(i).dy);
      }
    }
    canvas.drawPath(path, Paint()..color = fvTeal..strokeWidth = 2.5
      ..style = PaintingStyle.stroke..strokeCap = StrokeCap.round);
    canvas.drawCircle(coord(highlight), 4.5, Paint()..color = fvTeal);
    canvas.drawCircle(coord(highlight), 2, Paint()..color = Colors.white);
  }
  @override
  bool shouldRepaint(covariant _SeriesPainter old) {
    if (bars != old.bars || highlight != old.highlight || points.length != old.points.length ||
        breakBefore.length != old.breakBefore.length) return true;
    for (final index in breakBefore) {
      if (!old.breakBefore.contains(index)) return true;
    }
    for (var i = 0; i < points.length; i++) {
      if (points[i] != old.points[i]) return true;
    }
    return false;
  }
}
