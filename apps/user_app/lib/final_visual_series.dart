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
    this.intraday = false, this.showTable = true, this.markExtrema = false,
    this.tableSummary = FvTableSummary.latest, super.key});
  final List<dynamic> rows;
  final String label;
  final String unit;
  final double height;
  final bool bars;
  final bool dailyTable;
  final bool intraday;
  final bool showTable;
  final bool markExtrema;
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
    String stamp(DateTime value) {
      if (!widget.intraday) return value.toIso8601String().substring(0, 10);
      final taipei = value.toUtc().add(const Duration(hours: 8));
      return "${taipei.hour.toString().padLeft(2, '0')}:${taipei.minute.toString().padLeft(2, '0')}";
    }
    final highest = points.reduce((a, b) => a.$2 >= b.$2 ? a : b);
    final lowest = points.reduce((a, b) => a.$2 <= b.$2 ? a : b);
    final range = highest.$2 - lowest.$2;
    final currentLevel = range > 0
        ? (100 * (points.last.$2 - lowest.$2) / range).clamp(0.0, 100.0)
        : null;
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text(widget.label, style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800))),
        Text('有效 ${points.length} 期', style: const TextStyle(color: fvMuted, fontSize: 11)),
      ]),
      const SizedBox(height: 5),
      Text('${stamp(points.first.$1)} ～ ${stamp(points.last.$1)} · $unit',
        style: const TextStyle(color: fvMuted, fontSize: 11)),
      if (samples.any((sample) => sample.$2 == null))
        const Text('部分日期缺值，圖線不跨越缺口',
          style: TextStyle(color: fvMuted, fontSize: 11)),
      if (widget.intraday && widget.markExtrema) ...[
        const SizedBox(height: 8),
        Wrap(spacing: 14, runSpacing: 5, children: [
          Text('觀測高 ${legacy.accountingNumber(highest.$2, decimals: 2)} · ${stamp(highest.$1)}',
            key: const Key('intraday-observed-high'),
            style: const TextStyle(color: fvGain, fontWeight: FontWeight.w700, fontSize: 12)),
          Text('觀測低 ${legacy.accountingNumber(lowest.$2, decimals: 2)} · ${stamp(lowest.$1)}',
            key: const Key('intraday-observed-low'),
            style: const TextStyle(color: fvLoss, fontWeight: FontWeight.w700, fontSize: 12)),
          Text(currentLevel == null
              ? '區間位階：待形成高低區間'
              : '區間位階：${currentLevel.toStringAsFixed(1)}%',
            style: const TextStyle(color: fvInk, fontSize: 12)),
        ]),
        const Text('僅為頁面觸發後收集的分鐘點；未取樣時段不補點，不代表全天高低。',
            style: TextStyle(fontSize: 11, color: fvMuted)),
      ],
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
              painter: _SeriesPainter(points, index, breakBefore, widget.bars,
                  widget.intraday && widget.markExtrema))),
        ),
      )),
      const SizedBox(height: 8),
      Text('${stamp(points[index].$1)}：${legacy.accountingNumber(points[index].$2, decimals: 2)} $unit',
        key: const Key('fv-series-tooltip'),
        style: const TextStyle(color: fvInk, fontSize: 12, fontWeight: FontWeight.w700)),
      if (widget.showTable)
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
  const _SeriesPainter(this.points, this.highlight, this.breakBefore, this.bars, this.markExtrema);
  final List<(DateTime, double)> points;
  final int highlight;
  final Set<int> breakBefore;
  final bool bars;
  final bool markExtrema;
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
    if (markExtrema) {
      var highIndex = 0, lowIndex = 0;
      for (var i = 1; i < points.length; i++) {
        if (points[i].$2 > points[highIndex].$2) highIndex = i;
        if (points[i].$2 < points[lowIndex].$2) lowIndex = i;
      }
      canvas.drawCircle(coord(highIndex), 5, Paint()..color = fvGain);
      canvas.drawCircle(coord(lowIndex), 5, Paint()..color = fvLoss);
    }
    canvas.drawCircle(coord(highlight), 4.5, Paint()..color = fvTeal);
    canvas.drawCircle(coord(highlight), 2, Paint()..color = Colors.white);
  }
  @override
  bool shouldRepaint(covariant _SeriesPainter old) {
    if (bars != old.bars || markExtrema != old.markExtrema ||
        highlight != old.highlight || points.length != old.points.length ||
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


/// Bounded 09:00–13:30 TWSE trading-session progress chart.
///
/// Unlike a generic series, the horizontal coordinate is the actual clock
/// minute, not the position within the list of observed points. A missing
/// interval is never bridged or inferred; the 0% reference must come from a
/// verified, positive previous close supplied by the caller.
class FvIntradayProgressChart extends StatefulWidget {
  const FvIntradayProgressChart({
    required this.rows, required this.label, required this.unit,
    required this.previousClose, this.height = 200, super.key,
  });
  final List<dynamic> rows;
  final String label;
  final String unit;
  final double? previousClose;
  final double height;

  @override
  State<FvIntradayProgressChart> createState() => _FvIntradayProgressChartState();
}

typedef _SessionPoint = ({int minute, double price, double change});

class _FvIntradayProgressChartState extends State<FvIntradayProgressChart> {
  int? selectedMinute;
  static const int startMinute = 9 * 60;
  static const int endMinute = 13 * 60 + 30;

  String _time(int minute) =>
    '${(minute ~/ 60).toString().padLeft(2, '0')}:${(minute % 60).toString().padLeft(2, '0')}';

  String _percent(double value) =>
    '${value > 0 ? '+' : ''}${value.toStringAsFixed(2)}%';

  @override
  Widget build(BuildContext context) {
    final hasHistoricalBars = widget.rows.any((item) =>
        fvText(fvMap(item)['source'], missing: '') == 'shioaji_kbars');
    final previous = widget.previousClose;
    if (previous == null || !previous.isFinite || previous <= 0) {
      return fvPanel(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.label, style: const TextStyle(
              color: fvInk, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          const Text('前一正式收盤價缺值，無法計算 0% 基準與漲跌幅',
              key: Key('intraday-missing-previous-close'),
              style: TextStyle(color: fvMuted)),
        ],
      ));
    }
    // Convert source timestamps to Asia/Taipei before checking session window.
    // Prefer the latest dated session if a mixed-date response arrives.
    final dated = <({DateTime time, int minute, double price})>[];
    for (final raw in widget.rows) {
      final row = fvMap(raw);
      final utc = DateTime.tryParse(fvText(row['date'], missing: ''));
      final price = fvChartNumber(row['value']);
      if (utc == null || price == null || !price.isFinite || price <= 0) continue;
      final taipei = utc.toUtc().add(const Duration(hours: 8));
      final minute = taipei.hour * 60 + taipei.minute;
      if (minute < startMinute || minute > endMinute) continue;
      dated.add((time: taipei, minute: minute, price: price));
    }
    dated.sort((a, b) => a.time.compareTo(b.time));
    final newestDay = dated.isEmpty ? null :
      dated.last.time.year * 10000 + dated.last.time.month * 100 + dated.last.time.day;
    final byMinute = <int, double>{};
    for (final point in dated) {
      final day = point.time.year * 10000 + point.time.month * 100 + point.time.day;
      if (day == newestDay) byMinute[point.minute] = point.price;
    }
    final points = byMinute.entries.map((entry) =>
        (minute: entry.key, price: entry.value,
         change: (entry.value / previous - 1) * 100.0)).toList()
      ..sort((a, b) => a.minute.compareTo(b.minute));
    final high = points.isEmpty ? null :
      points.reduce((a, b) => b.price > a.price ? b : a);
    final low = points.isEmpty ? null :
      points.reduce((a, b) => b.price < a.price ? b : a);
    final latest = points.isEmpty ? null : points.last;
    final chosen = points.isEmpty ? null : selectedMinute == null ? latest :
      points.reduce((a, b) =>
        (b.minute - selectedMinute!).abs() < (a.minute - selectedMinute!).abs() ? b : a);
    final complete = points.isNotEmpty &&
        points.first.minute <= startMinute &&
        points.last.minute >= endMinute &&
        List.generate(points.length - 1, (i) =>
          points[i + 1].minute - points[i].minute).every((gap) => gap == 1);
    final gaps = points.length < 2 ? 0 :
      List.generate(points.length - 1, (i) => points[i + 1].minute - points[i].minute)
          .where((gap) => gap > 1).length;
    final progress = latest == null ? 0.0 :
      (latest.minute - startMinute) / (endMinute - startMinute) * 100.0;

    Widget extremum(String label, _SessionPoint? point, String key) {
      if (point == null) return const SizedBox.shrink();
      return Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: fvMuted, fontSize: 11)),
          const SizedBox(height: 2),
          Text(_time(point.minute), key: Key(key),
            style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
          Text('${legacy.accountingNumber(point.price, decimals: 2)} ${widget.unit}',
            style: const TextStyle(color: fvMuted, fontSize: 11)),
          Text(_percent(point.change), key: Key('$key-percent'),
            style: TextStyle(color: fvSignedColor(point.change),
                fontWeight: FontWeight.w800, fontSize: 12)),
        ],
      ));
    }

    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Expanded(child: Text(widget.label, style: const TextStyle(
              color: fvInk, fontWeight: FontWeight.w800))),
          Text('盤中進度 ${progress.toStringAsFixed(0)}%',
              key: const Key('intraday-session-progress'),
              style: const TextStyle(color: fvMuted, fontSize: 11)),
        ]),
        const SizedBox(height: 5),
        Text('09:00 起跑 → 13:30 終點 · 前收 ${legacy.accountingNumber(previous, decimals: 2)} ${widget.unit}',
          style: const TextStyle(color: fvMuted, fontSize: 11)),
        const SizedBox(height: 9),
        LayoutBuilder(builder: (context, bounds) => GestureDetector(
          onTapDown: (detail) {
            if (points.isEmpty) return;
            final fraction = ((detail.localPosition.dx - 45) /
                math.max(1.0, bounds.maxWidth - 58)).clamp(0.0, 1.0);
            setState(() => selectedMinute =
              startMinute + (fraction * (endMinute - startMinute)).round());
          },
          child: Semantics(
            label: '${widget.label}，09:00 至 13:30 固定時間軸，0% 前收基準，漲紅跌綠，可點選真實分鐘點',
            child: SizedBox(height: widget.height, width: double.infinity,
              child: CustomPaint(
                key: const Key('intraday-session-fixed-chart'),
                painter: _SessionProgressPainter(points, selectedMinute,
                    previous, fvGain, fvLoss),
              ),
            ),
          ),
        )),
        const SizedBox(height: 2),
        const Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('09:00', key: Key('session-start-0900'),
              style: TextStyle(color: fvMuted, fontSize: 11)),
          Text('10:30', style: TextStyle(color: fvMuted, fontSize: 11)),
          Text('12:00', style: TextStyle(color: fvMuted, fontSize: 11)),
          Text('13:30', key: Key('session-end-1330'),
              style: TextStyle(color: fvMuted, fontSize: 11)),
        ]),
        const SizedBox(height: 8),
        if (chosen != null)
          Text('觀測 ${_time(chosen.minute)}：${legacy.accountingNumber(chosen.price, decimals: 2)} ${widget.unit} · ${_percent(chosen.change)}',
            key: const Key('intraday-selected-observation'),
            style: TextStyle(color: fvSignedColor(chosen.change), fontSize: 12,
                fontWeight: FontWeight.w700)),
        if (points.isEmpty)
          const Text('今日尚無實際分鐘點，固定交易時段與 0% 線僅供參考',
              style: TextStyle(color: fvMuted, fontSize: 11)),
        if (points.length < 2 && points.isNotEmpty)
          const Text('只有一個觀測點，無法形成連續線段',
              style: TextStyle(color: fvMuted, fontSize: 11)),
        if (gaps > 0)
          Text('存在 $gaps 段超過 1 分鐘的缺口，線段不跨越缺口',
              key: const Key('intraday-session-gaps'),
              style: const TextStyle(color: fvMuted, fontSize: 11)),
        if (high != null && low != null && latest != null) ...[
          const Divider(height: 16),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            extremum(hasHistoricalBars ? '分鐘線最高' : '觀測最高', high, 'intraday-observed-high'),
            extremum(hasHistoricalBars ? '分鐘線最低' : '觀測最低', low, 'intraday-observed-low'),
            extremum('最新觀測', latest, 'intraday-observed-latest'),
          ]),
        ],
        const SizedBox(height: 6),
        Text(complete
            ? '已涵蓋所需交易時段的觀測分鐘點；不代表逐筆成交最高／最低。'
            : (hasHistoricalBars
            ? '含券商歷史 1 分 K 收盤價（非即時）、即時觀測；高低只統計有資料的分鐘收盤價，非逐筆成交高低。'
            : '僅統計實際收集的分鐘點，高低時間與漲跌幅不代表全天完整行情。'),
          style: const TextStyle(color: fvMuted, fontSize: 10)),
      ],
    ));
  }
}

class _SessionProgressPainter extends CustomPainter {
  const _SessionProgressPainter(this.points, this.selectedMinute,
      this.previousClose, this.gainColor, this.lossColor);
  final List<_SessionPoint> points;
  final int? selectedMinute;
  final double previousClose;
  final Color gainColor;
  final Color lossColor;
  static const int start = 9 * 60;
  static const int end = 13 * 60 + 30;
  static const double left = 45;
  static const double right = 13;
  static const double top = 16;
  static const double bottom = 13;

  @override
  void paint(Canvas canvas, Size size) {
    final width = math.max(1.0, size.width - left - right);
    final height = math.max(1.0, size.height - top - bottom);
    final largest = points.fold<double>(0, (v, p) => math.max(v, p.change.abs()));
    // Symmetric percent range: the 0% previous-close line is always central.
    final amplitude = math.max(0.3, largest * 1.15);
    final zeroY = top + height / 2;
    double x(int minute) => left + (minute - start) / (end - start) * width;
    double y(double change) => zeroY - change / amplitude * height / 2;
    Offset offset(_SessionPoint p) => Offset(x(p.minute), y(p.change));
    final axis = Paint()..color = fvSoft..strokeWidth = 1.0;
    canvas.drawLine(Offset(left, top), Offset(left, top + height), axis);
    canvas.drawLine(Offset(left + width, top), Offset(left + width, top + height), axis);
    canvas.drawLine(Offset(left, top), Offset(left + width, top), axis);
    canvas.drawLine(Offset(left, top + height), Offset(left + width, top + height), axis);
    // Neutral zero line, rendered with explicit dash to distinguish from data.
    final reference = Paint()..color = fvMuted..strokeWidth = 1.2;
    for (double at = left; at < left + width; at += 10) {
      canvas.drawLine(Offset(at, zeroY),
          Offset(math.min(at + 5, left + width), zeroY), reference);
    }
    void label(String value, double placeY) {
      final painter = TextPainter(
          text: TextSpan(text: value,
              style: const TextStyle(color: fvMuted, fontSize: 10)),
          textDirection: TextDirection.ltr)..layout();
      painter.paint(canvas, Offset(1, placeY - painter.height / 2));
    }
    label('+${amplitude.toStringAsFixed(1)}%', top);
    label('0%', zeroY);
    label('-${amplitude.toStringAsFixed(1)}%', top + height);
    // The not-yet-observed future is visibly empty rather than stretched.
    if (points.isNotEmpty) {
      final progressX = x(points.last.minute);
      canvas.drawLine(Offset(progressX, top), Offset(progressX, top + height),
          Paint()..color = fvSoft..strokeWidth = 1);
    }
    void draw(Offset a, Offset b, Color color) {
      canvas.drawLine(a, b, Paint()
        ..color = color..strokeWidth = 2.7..strokeCap = StrokeCap.round);
    }
    for (var i = 1; i < points.length; i++) {
      final before = points[i - 1], after = points[i];
      // 1–2 minute observations can form a segment; longer gaps stay blank.
      if (after.minute - before.minute > 1) continue;
      final a = offset(before), b = offset(after);
      if (before.change * after.change < 0) {
        final fraction = before.change.abs() /
            (before.change.abs() + after.change.abs());
        final crossing = Offset(a.dx + (b.dx - a.dx) * fraction, zeroY);
        draw(a, crossing, before.change > 0 ? gainColor : lossColor);
        draw(crossing, b, after.change > 0 ? gainColor : lossColor);
      } else {
        final sign = before.change == 0 ? after.change : before.change;
        draw(a, b, sign > 0 ? gainColor :
            sign < 0 ? lossColor : fvMuted);
      }
    }
    if (points.isNotEmpty) {
      final selected = selectedMinute == null ? points.last : points.reduce(
        (a, b) => (b.minute - selectedMinute!).abs() <
            (a.minute - selectedMinute!).abs() ? b : a);
      final highlight = offset(selected);
      canvas.drawCircle(highlight, 4.4,
          Paint()..color = selected.change > 0 ? gainColor :
            selected.change < 0 ? lossColor : fvMuted);
      canvas.drawCircle(highlight, 2.0, Paint()..color = Colors.white);
    }
  }
  @override
  bool shouldRepaint(covariant _SessionProgressPainter old) {
    if (selectedMinute != old.selectedMinute ||
        previousClose != old.previousClose || points.length != old.points.length ||
        gainColor != old.gainColor || lossColor != old.lossColor) return true;
    for (var i = 0; i < points.length; i++) {
      if (points[i] != old.points[i]) return true;
    }
    return false;
  }
}
