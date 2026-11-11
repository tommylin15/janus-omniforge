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
/// interval is never bridged or inferred. Missing official previous-close data
/// switches to a raw-price axis; it never suppresses genuine observations or
/// invents a 0% baseline.
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

/// Scale measured minute prices and the verified previous-close 0% reference.
class FvIntradayAxisRange {
  const FvIntradayAxisRange(this.min, this.max);
  final double min;
  final double max;
}

FvIntradayAxisRange fvIntradayAxisRange(Iterable<double> changes) {
  var minValue = 0.0, maxValue = 0.0;
  for (final change in changes) {
    if (!change.isFinite) continue;
    minValue = math.min(minValue, change);
    maxValue = math.max(maxValue, change);
  }
  final mid = (minValue + maxValue) / 2;
  final span = math.max(0.6, maxValue - minValue);
  final padding = math.max(0.09, span * 0.08);
  return FvIntradayAxisRange(mid - span / 2 - padding, mid + span / 2 + padding);
}

/// Raw-price fallback is used only when there is no verified zero reference.
/// Its range depends on observed prices, never an invented closing price.
FvIntradayAxisRange fvIntradayPriceAxisRange(Iterable<double> prices) {
  final valid = prices.where((price) => price.isFinite && price > 0).toList();
  if (valid.isEmpty) return const FvIntradayAxisRange(0, 1);
  final low = valid.reduce(math.min);
  final high = valid.reduce(math.max);
  final padding = math.max(0.05, math.max((high - low) * 0.08, high * 0.002));
  return FvIntradayAxisRange(low - padding, high + padding);
}

typedef _SessionPoint = ({int minute, double price, double change});
typedef _MinuteVolume = ({int minute, double volume});

class _FvIntradayProgressChartState extends State<FvIntradayProgressChart> {
  int? selectedMinute;
  bool showChartNotes = false;
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
    final hasReference = previous != null && previous.isFinite && previous > 0;
    // Convert source timestamps to Asia/Taipei before checking session window.
    // Prefer the latest dated session if a mixed-date response arrives.
    final dated = <({DateTime time, int minute, double price, double? volume})>[];
    for (final raw in widget.rows) {
      final row = fvMap(raw);
      final utc = DateTime.tryParse(fvText(row['date'], missing: ''));
      final price = fvChartNumber(row['value']);
      if (utc == null || price == null || !price.isFinite || price <= 0) continue;
      final taipei = utc.toUtc().add(const Duration(hours: 8));
      final minute = taipei.hour * 60 + taipei.minute;
      if (minute < startMinute || minute > endMinute) continue;
      // Quote samples have no reliable minute volume. Preserve only real Kbars.
      final reportedVolume = row['source'] == 'shioaji_kbars'
          ? fvNumber(row['volume']) : null;
      final volume = reportedVolume != null && reportedVolume.isFinite &&
              reportedVolume >= 0 ? reportedVolume : null;
      dated.add((time: taipei, minute: minute, price: price, volume: volume));
    }
    dated.sort((a, b) => a.time.compareTo(b.time));
    final newestDay = dated.isEmpty ? null :
      dated.last.time.year * 10000 + dated.last.time.month * 100 + dated.last.time.day;
    final byMinute = <int, ({double price, double? volume})>{};
    for (final point in dated) {
      final day = point.time.year * 10000 + point.time.month * 100 + point.time.day;
      if (day == newestDay) {
        byMinute[point.minute] = (price: point.price, volume: point.volume);
      }
    }
    final points = byMinute.entries.map((entry) =>
        (minute: entry.key, price: entry.value.price,
         change: hasReference
             ? (entry.value.price / previous! - 1) * 100.0
             : entry.value.price)).toList()
      ..sort((a, b) => a.minute.compareTo(b.minute));
    final volumePoints = byMinute.entries
        .where((e) => e.value.volume != null)
        .map((e) => (minute: e.key, volume: e.value.volume!))
        .toList()..sort((a, b) => a.minute.compareTo(b.minute));
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

    // Keep price, extrema and their actual observation times above the graph.
    Widget extremum(String label, _SessionPoint? point, String key) {
      if (point == null) return const Expanded(child: SizedBox.shrink());
      return Expanded(child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 3),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min, children: [
          Text(label, maxLines: 1, overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: fvMuted, fontSize: 12)),
          Align(alignment: Alignment.centerLeft,
            child: FittedBox(fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(legacy.accountingNumber(point.price, decimals: 2),
                maxLines: 1, softWrap: false,
                style: const TextStyle(color: fvInk,
                  fontWeight: FontWeight.w800, fontSize: 17)),
            ),
          ),
          Text(_time(point.minute), key: Key(key),
            style: const TextStyle(color: fvMuted,
                fontWeight: FontWeight.w600, fontSize: 12)),
          if (hasReference)
            Text(_percent(point.change), key: Key('$key-percent'),
              style: TextStyle(color: fvSignedColor(point.change),
                fontWeight: FontWeight.w800, fontSize: 13)),
        ]),
      ));
    }

    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Expanded(child: Text(widget.label, maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: fvInk, fontSize: 17,
              fontWeight: FontWeight.w800))),
          Text('盤中進度 ${progress.toStringAsFixed(0)}%',
              key: const Key('intraday-session-progress'),
              style: const TextStyle(color: fvMuted, fontSize: 12)),
        ]),
        const SizedBox(height: 5),
        Text(hasReference
            ? '09:00–13:30 · 前收 ${legacy.accountingNumber(previous, decimals: 2)} ${widget.unit} · 0% 基準'
            : '09:00–13:30 · 實際分鐘價格 · 無 0% 基準',
          style: const TextStyle(color: fvMuted, fontSize: 12)),
        if (!hasReference)
          const Padding(padding: EdgeInsets.only(top: 4),
            child: Text('前一正式收盤價缺值：仍顯示實際價格，不計算漲跌幅',
              key: Key('intraday-missing-previous-close'),
              style: TextStyle(color: fvMuted, fontSize: 12))),
        if (high != null && low != null && latest != null) ...[
          const SizedBox(height: 9),
          Container(
            key: const Key('intraday-top-summary'),
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 7),
            decoration: BoxDecoration(
              color: fvCanvas,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              extremum('最新', latest, 'intraday-observed-latest'),
              extremum(hasHistoricalBars ? '分鐘最高' : '觀測最高', high, 'intraday-observed-high'),
              extremum(hasHistoricalBars ? '分鐘最低' : '觀測最低', low, 'intraday-observed-low'),
            ]),
          ),
        ],
        if (selectedMinute != null && chosen != null)
          Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Text('選取 ${_time(chosen.minute)}：${legacy.accountingNumber(chosen.price, decimals: 2)} ${widget.unit}${hasReference ? ' · ${_percent(chosen.change)}' : ''}',
              key: const Key('intraday-selected-observation'),
              style: TextStyle(color: fvSignedColor(chosen.change),
                  fontSize: 13, fontWeight: FontWeight.w700)),
          ),
        const SizedBox(height: 8),
        LayoutBuilder(builder: (context, bounds) => GestureDetector(
          onTapDown: (detail) {
            if (points.isEmpty) return;
            final fraction = ((detail.localPosition.dx - 45) /
                math.max(1.0, bounds.maxWidth - 58)).clamp(0.0, 1.0);
            setState(() => selectedMinute =
              startMinute + (fraction * (endMinute - startMinute)).round());
          },
          onHorizontalDragUpdate: (detail) {
            if (points.isEmpty) return;
            final fraction = ((detail.localPosition.dx - 45) /
                math.max(1.0, bounds.maxWidth - 58)).clamp(0.0, 1.0);
            final target =
                startMinute + (fraction * (endMinute - startMinute)).round();
            if (target != selectedMinute) setState(() => selectedMinute = target);
          },
          child: Semantics(
            label: '${widget.label}，09:00 至 13:30 固定時間軸，${hasReference ? '0% 前收基準，漲紅跌綠' : '前收缺值，原始價格走勢'}，可點選真實分鐘點',
            child: SizedBox(height: widget.height, width: double.infinity,
              child: TweenAnimationBuilder<double>(
                // Animate the actual newest point once on data update, not a
                // perpetual pulse that could imply fresh quote activity.
                key: ValueKey('intraday-point-${latest?.minute ?? -1}'),
                tween: Tween<double>(begin: 0.65, end: 1.0),
                duration: const Duration(milliseconds: 320),
                curve: Curves.easeOutCubic,
                builder: (context, pointEmphasis, child) => CustomPaint(
                  key: const Key('intraday-session-fixed-chart'),
                  painter: _SessionProgressPainter(points, selectedMinute,
                      previous, fvGain, fvLoss, pointEmphasis),
                ),
              ),
            ),
          ),
        )),
        if (volumePoints.isNotEmpty) ...[
          const SizedBox(height: 7),
          const Text('分鐘成交量 · 券商 K 棒原始單位',
              key: Key('intraday-volume-title'),
              style: TextStyle(fontSize: 12, color: fvMuted)),
          SizedBox(height: 38, width: double.infinity,
            child: CustomPaint(
              key: const Key('intraday-session-volume-chart'),
              painter: _SessionVolumePainter(volumePoints),
            )),
        ] else
          const Padding(
            padding: EdgeInsets.only(top: 5),
            child: Text('分鐘成交量尚無可信來源，不估算或填補',
              key: Key('intraday-volume-missing'),
              style: TextStyle(fontSize: 12, color: fvMuted)),
          ),
        const SizedBox(height: 2),
        const Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('09:00', key: Key('session-start-0900'),
              style: TextStyle(color: fvMuted, fontSize: 11)),
          Text('10:30', style: TextStyle(color: fvMuted, fontSize: 11)),
          Text('12:00', style: TextStyle(color: fvMuted, fontSize: 11)),
          Text('13:30', key: Key('session-end-1330'),
              style: TextStyle(color: fvMuted, fontSize: 11)),
        ]),
        if (points.isEmpty)
          const Text('今日尚無實際分鐘點；不補假行情',
              key: Key('intraday-empty-points'),
              style: TextStyle(color: fvMuted, fontSize: 12)),
        if (points.length == 1)
          const Text('只有一個觀測點，無法形成連續線段',
              style: TextStyle(color: fvMuted, fontSize: 12)),
        if (gaps > 0)
          Text('存在 $gaps 段超過 1 分鐘的缺口，線段不跨越缺口',
              key: const Key('intraday-session-gaps'),
              style: const TextStyle(color: fvMuted, fontSize: 12)),
        Align(alignment: Alignment.centerRight,
          child: TextButton.icon(
            key: const Key('intraday-chart-notes-toggle'),
            onPressed: () => setState(() => showChartNotes = !showChartNotes),
            icon: Icon(showChartNotes
                ? Icons.expand_less : Icons.info_outline, size: 16),
            label: Text(showChartNotes ? '收起資料說明' : '資料說明',
                style: const TextStyle(fontSize: 12)),
          ),
        ),
        if (showChartNotes)
          Padding(padding: const EdgeInsets.only(bottom: 5),
            child: Text(complete
                ? '已涵蓋所需交易時段的觀測分鐘點；不代表逐筆成交最高／最低。'
                : (hasHistoricalBars
                  ? '含券商歷史 1 分 K 收盤價（非即時）及即時觀測；高低只統計有資料的分鐘收盤價，非逐筆成交高低。'
                  : '僅統計實際收集的分鐘點，高低時間與漲跌幅不代表全天完整行情。'),
              style: const TextStyle(color: fvMuted, fontSize: 12)),
          ),
      ],
    ));
  }
}

class _SessionProgressPainter extends CustomPainter {
  const _SessionProgressPainter(this.points, this.selectedMinute,
      this.previousClose, this.gainColor, this.lossColor, this.pointEmphasis);
  final List<_SessionPoint> points;
  final int? selectedMinute;
  final double? previousClose;
  final Color gainColor;
  final Color lossColor;
  final double pointEmphasis;
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
    final hasReference = previousClose != null && previousClose!.isFinite && previousClose! > 0;
    final range = hasReference
        ? fvIntradayAxisRange(points.map((p) => p.change))
        : fvIntradayPriceAxisRange(points.map((p) => p.price));
    double x(int minute) => left + (minute - start) / (end - start) * width;
    double y(double change) =>
        top + (range.max - change) / (range.max - range.min) * height;
    final zeroY = hasReference ? y(0) : top + height;
    Offset offset(_SessionPoint p) => Offset(x(p.minute), y(p.change));
    final axis = Paint()..color = fvSoft..strokeWidth = 1.0;
    canvas.drawLine(Offset(left, top), Offset(left, top + height), axis);
    canvas.drawLine(Offset(left + width, top), Offset(left + width, top + height), axis);
    canvas.drawLine(Offset(left, top), Offset(left + width, top), axis);
    canvas.drawLine(Offset(left, top + height), Offset(left + width, top + height), axis);
    // Faint reading guides orient prices without competing with the series.
    final guide = Paint()
      ..color = fvMuted.withValues(alpha: 0.10)
      ..strokeWidth = 0.7;
    for (final fraction in [0.25, 0.75]) {
      final guideY = top + height * fraction;
      canvas.drawLine(Offset(left, guideY),
          Offset(left + width, guideY), guide);
    }
    for (final minute in [10 * 60 + 30, 12 * 60]) {
      final guideX = x(minute);
      canvas.drawLine(Offset(guideX, top),
          Offset(guideX, top + height), guide);
    }
    // The dashed zero line is shown only with an authenticated dated reference.
    if (hasReference) {
      final reference = Paint()..color = fvMuted..strokeWidth = 1.2;
      for (double at = left; at < left + width; at += 10) {
        canvas.drawLine(Offset(at, zeroY),
            Offset(math.min(at + 5, left + width), zeroY), reference);
      }
    }
    void label(String value, double placeY) {
      final painter = TextPainter(
          text: TextSpan(text: value,
              style: const TextStyle(color: fvMuted, fontSize: 10)),
          textDirection: TextDirection.ltr)..layout();
      painter.paint(canvas, Offset(1, placeY - painter.height / 2));
    }
    // Price labels remain meaningful without a prior close; only the
    // percentage transformation and dashed baseline are omitted then.
    String axisPrice(double value) => legacy.accountingNumber(
        hasReference ? previousClose! * (1 + value / 100) : value,
        decimals: (hasReference ? previousClose! : value) >= 1000 ? 0 : 2);
    label(axisPrice(range.max), top);
    if (hasReference) label('0%', zeroY);
    label(axisPrice(range.min), top + height);
    // The not-yet-observed future is visibly empty rather than stretched.
    if (points.isNotEmpty) {
      final progressX = x(points.last.minute);
      canvas.drawLine(Offset(progressX, top), Offset(progressX, top + height),
          Paint()..color = fvSoft..strokeWidth = 1);
    }
    // Translucent fills are confined to each observed one-minute segment.
    // They never bridge missing minutes or paint into the future region.
    void fillSegment(Offset a, Offset b, Color color) {
      final path = Path()
        ..moveTo(a.dx, zeroY)
        ..lineTo(a.dx, a.dy)
        ..lineTo(b.dx, b.dy)
        ..lineTo(b.dx, zeroY)
        ..close();
      canvas.drawPath(path, Paint()..color = color.withValues(alpha: 0.055));
    }
    void draw(Offset a, Offset b, Color color) {
      canvas.drawLine(a, b, Paint()
        ..color = color
        ..strokeWidth = 1.7
        ..strokeCap = StrokeCap.round);
    }
    for (var i = 1; i < points.length; i++) {
      final before = points[i - 1], after = points[i];
      if (after.minute - before.minute > 1) continue;
      final a = offset(before), b = offset(after);
      if (!hasReference) {
        draw(a, b, fvTeal);
        continue;
      }
      if (before.change * after.change < 0) {
        final fraction = before.change.abs() /
            (before.change.abs() + after.change.abs());
        final crossing = Offset(a.dx + (b.dx - a.dx) * fraction, zeroY);
        final colorA = before.change > 0 ? gainColor : lossColor;
        final colorB = after.change > 0 ? gainColor : lossColor;
        fillSegment(a, crossing, colorA);
        fillSegment(crossing, b, colorB);
        draw(a, crossing, colorA);
        draw(crossing, b, colorB);
      } else {
        final sign = before.change == 0 ? after.change : before.change;
        final color = sign > 0 ? gainColor :
            sign < 0 ? lossColor : fvMuted;
        fillSegment(a, b, color);
        draw(a, b, color);
      }
    }
    if (points.isNotEmpty) {
      final selected = selectedMinute == null ? points.last : points.reduce(
        (a, b) => (b.minute - selectedMinute!).abs() <
            (a.minute - selectedMinute!).abs() ? b : a);
      final highlight = offset(selected);
      final selectedColor = !hasReference ? fvTeal :
          selected.change > 0 ? gainColor :
          selected.change < 0 ? lossColor : fvMuted;
      // Soft halo emphasizes the last recorded point, not live activity.
      final haloRadius = selectedMinute == null
          ? 8.0 * pointEmphasis : 7.0;
      canvas.drawCircle(highlight, haloRadius,
          Paint()..color = selectedColor.withValues(alpha: 0.13));
      canvas.drawCircle(highlight, 3.6, Paint()..color = selectedColor);
      canvas.drawCircle(highlight, 1.5, Paint()..color = Colors.white);
    }
  }
  @override
  bool shouldRepaint(covariant _SessionProgressPainter old) {
    if (selectedMinute != old.selectedMinute ||
        previousClose != old.previousClose || points.length != old.points.length ||
        gainColor != old.gainColor || lossColor != old.lossColor ||
        pointEmphasis != old.pointEmphasis) return true;
    for (var i = 0; i < points.length; i++) {
      if (points[i] != old.points[i]) return true;
    }
    return false;
  }
}



/// Provider-authored minute Kbar volumes, aligned with the same clock axis.
class _SessionVolumePainter extends CustomPainter {
  const _SessionVolumePainter(this.values);
  final List<_MinuteVolume> values;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 45.0, right = 13.0;
    final width = math.max(1.0, size.width - left - right);
    final baseline = size.height - 5;
    final availableHeight = math.max(1.0, size.height - 10);
    final largest = values.fold<double>(0, (v, p) => math.max(v, p.volume));
    final axis = Paint()..color = fvSoft..strokeWidth = 1;
    canvas.drawLine(Offset(left, baseline), Offset(left + width, baseline), axis);
    if (largest <= 0) return;
    final paint = Paint()..color = fvTeal.withValues(alpha: .65);
    final barWidth = math.max(1.0, width / 270 * .72);
    for (final point in values) {
      final x = left + (point.minute - 540) / 270 * width;
      final barHeight = point.volume / largest * availableHeight;
      canvas.drawRect(
        Rect.fromLTWH(x - barWidth / 2, baseline - barHeight, barWidth, barHeight),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _SessionVolumePainter old) {
    if (values.length != old.values.length) return true;
    for (var i = 0; i < values.length; i++) {
      if (old.values[i] != values[i]) return true;
    }
    return false;
  }
}
