import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'final_visual_common.dart';
import 'final_charts.dart' show fvChartNumber;

class ModelTimelinePanel extends StatefulWidget {
  const ModelTimelinePanel(this.payload, {super.key});
  final Map<String, dynamic> payload;

  @override
  State<ModelTimelinePanel> createState() => _ModelTimelinePanelState();
}

class _ModelTimelinePanelState extends State<ModelTimelinePanel> {
  String selected = 'risk';
  Map<String, dynamic> get payload => widget.payload;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('模型要回答什麼，後來發生了什麼？',
              style: TextStyle(
                  color: fvInk, fontSize: 18, fontWeight: FontWeight.w800)),
          const Text('藍線是實際資料，橘色虛線與圓點是當時保存的模型結果。未到期的結果不評分；缺資料不補線。',
              style: TextStyle(color: fvMuted, fontSize: 12)),
          if (payload['status'] == 'unavailable')
            fvBoundedState('模型歷史暫時無法讀取；最新報告仍可閱讀，請重新讀取狀態。'),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final role in const {
              'risk': '波動風險',
              'quant': '股價方向',
              'fundamental': '公司營運',
              'valuation': '價格評價'
            }.entries)
              ChoiceChip(
                  key: Key('model-role-${role.key}'),
                  label: Text(role.value),
                  selected: selected == role.key,
                  onSelected: (_) => setState(() => selected = role.key)),
          ]),
          for (final entry in const {
            'quant': (
              '股價方向｜Quant',
              '未來 20 個交易日會上漲嗎？',
              '上漲機率／結果（%）',
              '橘線是模型的上漲機率；藍點 100 表示該 20 日最後收盤高於起點，0 表示沒有。單次結果不是「實際機率」，需累積多次才能判讀效果。'
            ),
            'risk': (
              '波動風險｜Risk',
              '未來 20 個交易日的波動會有多大？',
              '年化波動（%）',
              '兩線依 20 日期間的結束日對齊。藍線是實際 20 日波動，橘線是起點當時的預測。36% 是年化波動，不是未來會漲跌 36%。'
            ),
            'fundamental': (
              '公司營運｜Fundamental',
              '下個月營收比去年同月成長多少？',
              '營收年增率（%）',
              '按營收月份對齊預測與公布值。模型預測的是營收年增率，不是 EPS；可回到營運區核對營收與獲利。'
            ),
            'valuation_pe': (
              '價格評價｜Valuation・PE',
              '價格相對公司獲利，落在哪個倍數？',
              '本益比（倍）',
              '比較模型推估 PE 與市場實際 PE。模型原生 log(PE) 已轉回倍數；它是估值參考，不是未來股價預測或保證目標價。'
            ),
            'valuation_pb': (
              '價格評價｜Valuation・PB',
              '價格相對公司淨值，落在哪個倍數？',
              '股價淨值比（倍）',
              'PB 與 PE 分開比較，避免不同口徑混成一個分數。財務更新慢於股價；來源日期與模型版本可在下方核對。'
            ),
          }.entries.where((e) =>
              e.key == selected ||
              (selected == 'valuation' && e.key.startsWith('valuation_'))))
            _TimelineCard(
                entry.key,
                entry.value,
                fvMap(fvMap(payload['roles'])[entry.key]),
                fvText(payload['as_of'], missing: ''),
                key: ValueKey(entry.key)),
          Text(
              '實際資料來源：${fvRows(payload['source_ids']).join('、')}。原始價格未還原除權息，期間內公司行動可能影響比較。',
              style: const TextStyle(color: fvMuted, fontSize: 11)),
        ],
      );
}

class _TimelineCard extends StatelessWidget {
  const _TimelineCard(this.role, this.copy, this.data, this.asOf, {super.key});
  final String role, asOf;
  final (String, String, String, String) copy;
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final observed = fvRows(data['observed']).map(fvMap).toList();
    final forecasts = fvRows(data['forecasts']).map(fvMap).toList();
    final grid = <String, Map<String, dynamic>>{};
    for (final row in observed) {
      final day = fvText(row['date'], missing: '');
      grid.putIfAbsent(day, () => {'date': day})['actual'] =
          fvChartNumber(row['value']);
    }
    for (final row in forecasts) {
      final day = fvText(row['date'], missing: '');
      grid.putIfAbsent(day, () => {'date': day})
        ..['forecast'] = fvChartNumber(row['value'])
        ..['version'] = row['model_version']
        ..['signal_date'] = row['signal_date']
        ..['published_date'] = row['published_date'];
    }
    final rows = grid.values.toList()
      ..sort((a, b) => '${a['date']}'.compareTo('${b['date']}'));
    final visible = rows.length > 60 ? rows.sublist(rows.length - 60) : rows;
    final latest = forecasts.isEmpty ? <String, dynamic>{} : forecasts.last;
    final prediction = fvChartNumber(latest['value']);
    final actual = fvChartNumber(latest['actual']);
    final recent =
        observed.isEmpty ? null : fvChartNumber(observed.last['value']);
    final observedDate =
        observed.isEmpty ? null : DateTime.tryParse('${observed.last['date']}');
    final evaluationDate = DateTime.tryParse(asOf);
    final recentRisk = observedDate != null &&
        evaluationDate != null &&
        evaluationDate.difference(observedDate).inDays >= 0 &&
        evaluationDate.difference(observedDate).inDays <= 7;
    final currentForecast = asOf.length >= 7 &&
        fvText(latest['date'], missing: '').compareTo(
                role == 'fundamental' ? asOf.substring(0, 7) : asOf) >=
            0;
    final matched =
        forecasts.where((p) => fvChartNumber(p['actual']) != null).length;
    final retrospective =
        forecasts.any((p) => p['evaluation_kind'] == 'retrospective');
    return Padding(
        padding: const EdgeInsets.only(top: 12),
        child: fvPanel(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(copy.$1,
                style:
                    const TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
            Text(copy.$2, style: const TextStyle(color: fvInk, fontSize: 16)),
            const SizedBox(height: 8),
            Text(copy.$3, style: const TextStyle(color: fvMuted, fontSize: 12)),
            if (visible.isNotEmpty) ...[
              Semantics(
                  label: '${copy.$1}實際與模型歷史；數值可展開對照表閱讀',
                  child: SizedBox(
                      height: 180,
                      width: double.infinity,
                      child: CustomPaint(
                          key: Key('model-timeline-$role'),
                          painter: _TimelinePainter(
                              visible, asOf, role == 'quant')))),
              Wrap(spacing: 16, runSpacing: 4, children: [
                Text(
                    '實際 · ${visible.first['date']} ～ ${observed.isEmpty ? '尚無' : observed.last['date']}',
                    style: const TextStyle(
                        color: Color(0xFF1565C0), fontSize: 11)),
                const Text('模型 · 橘色虛線／圓點',
                    style: TextStyle(color: Color(0xFFBF5B16), fontSize: 11)),
              ]),
            ] else
              const Text('目前沒有可畫的歷史資料。缺少已保存預測或對應實際值，不以示意圖替代。'),
            const SizedBox(height: 8),
            if (prediction != null) ...[
              Text(
                  '最新對照期 ${fvText(latest['date'])} · 模型 ${prediction.toStringAsFixed(2)}',
                  style: const TextStyle(fontWeight: FontWeight.w700)),
              Text(actual == null
                  ? '對應實際值尚未公布、期間未到期或行情不足，暫不能判斷預測效果。'
                  : role == 'quant'
                      ? '該期結果：${actual == 100 ? '上漲' : '未上漲'}，實際報酬 ${fvChartNumber(latest['actual_return_percent'])?.toStringAsFixed(2) ?? '—'}%。一次結果不能證明模型準確。'
                      : '對應實際 ${actual.toStringAsFixed(2)}；模型${prediction > actual ? '高估' : prediction < actual ? '低估' : '接近'} ${((prediction - actual).abs()).toStringAsFixed(2)} ${role.startsWith('valuation') ? '倍' : '個百分點'}。'),
              if (actual == null &&
                  recent != null &&
                  currentForecast &&
                  recentRisk &&
                  role == 'risk')
                Text(
                    '最近實際波動 ${recent.toStringAsFixed(2)}%，下一段預測 ${prediction.toStringAsFixed(2)}%：'
                    '${prediction > recent ? '預期震盪擴大，留意持倉承受度' : '預期震盪未擴大，仍不代表價格一定上漲'}。'),
              if (actual == null &&
                  recent != null &&
                  currentForecast &&
                  role == 'fundamental')
                Text(
                    '最近公布營收年增 ${recent.toStringAsFixed(2)}%，模型預估下個月 ${prediction.toStringAsFixed(2)}%；'
                    '預期成長${prediction > recent ? '加快' : '放緩或持平'}，需等該月公告確認。'),
            ],
            if (forecasts.isEmpty)
              const Text('尚無已保存的有效模型歷史；已有實際資料照常呈現，不能據此宣稱模型有效。'),
            Text(
                '保存預測 ${forecasts.length} 筆 · 可對照 $matched 筆 · 待實際值 ${fvInt(data['pending'])} 筆 · 缺輸入／停用 ${fvInt(data['missing'])} 筆',
                style: const TextStyle(color: fvMuted, fontSize: 11)),
            if (retrospective)
              const Text('部分結果晚於輸入日才保存，屬事後重算對照，不能冒稱當時已發布的預測或前瞻驗證。',
                  style: TextStyle(color: fvMuted, fontSize: 12)),
            Text(copy.$4, style: const TextStyle(color: fvMuted, fontSize: 12)),
            if (visible.isNotEmpty)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('日期、數值與模型版本'),
                children: [
                  for (final row in visible.reversed.take(20))
                    ListTile(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: Text(
                            '${row['date']} · 實際 ${fvChartNumber(row['actual'])?.toStringAsFixed(2) ?? '—'} · 模型 ${fvChartNumber(row['forecast'])?.toStringAsFixed(2) ?? '—'}'),
                        subtitle: row['version'] == null
                            ? null
                            : Text(
                                '${row['version']} · 輸入 ${fvText(row['signal_date'])} · 保存 ${fvText(row['published_date'])}')),
                  if (latest.isNotEmpty)
                    Text(
                        '最新輸入日 ${fvText(latest['signal_date'])} · 保存日 ${fvText(latest['published_date'])}'),
                ],
              ),
          ]),
        ));
  }
}

class _TimelinePainter extends CustomPainter {
  const _TimelinePainter(this.rows, this.asOf, this.binary);
  final List<Map<String, dynamic>> rows;
  final String asOf;
  final bool binary;

  @override
  void paint(Canvas canvas, Size size) {
    final values = [
      for (final r in rows) ...[
        fvChartNumber(r['actual']),
        fvChartNumber(r['forecast'])
      ]
    ].whereType<double>().toList();
    if (values.isEmpty) return;
    final low = values.reduce(math.min), high = values.reduce(math.max);
    final span = high == low ? math.max(high.abs() * .1, 1.0) : high - low;
    final first = DateTime.parse(
        '${rows.first['date']}${'${rows.first['date']}'.length == 7 ? '-01' : ''}');
    final last = DateTime.parse(
        '${rows.last['date']}${'${rows.last['date']}'.length == 7 ? '-01' : ''}');
    Offset point(int i, double v) {
      final day = '${rows[i]['date']}';
      final date = DateTime.parse('$day${day.length == 7 ? '-01' : ''}');
      final fraction = last == first
          ? .5
          : date.difference(first).inDays / last.difference(first).inDays;
      return Offset(44 + fraction * (size.width - 52),
          12 + (high - v) / span * (size.height - 38));
    }

    final cutoff = DateTime.tryParse(asOf);
    if (cutoff != null && last.isAfter(cutoff)) {
      final x = last == first
          ? 44.0
          : (44 +
                  cutoff.difference(first).inDays /
                      last.difference(first).inDays *
                      (size.width - 52))
              .clamp(44.0, size.width - 8);
      canvas.drawRect(Rect.fromLTRB(x, 0, size.width, size.height - 22),
          Paint()..color = const Color(0xFFFFF4E8));
    }
    for (final (text, x) in [
      ('${rows.first['date']}', 44.0),
      ('${rows.last['date']}', math.max(44.0, size.width - 72)),
    ]) {
      final label = TextPainter(
          text: TextSpan(
              text: text,
              style: const TextStyle(
                  fontSize: 10, color: fvMuted, fontFamily: 'Roboto')),
          textDirection: TextDirection.ltr)
        ..layout();
      label.paint(canvas, Offset(x, size.height - 14));
    }

    for (final v in [high, low]) {
      final y = 12 + (high - v) / span * (size.height - 38);
      canvas.drawLine(
          Offset(42, y), Offset(size.width, y), Paint()..color = fvSoft);
      final text = TextPainter(
          text: TextSpan(
              text: v.toStringAsFixed(1),
              style: const TextStyle(
                  fontSize: 10, color: fvMuted, fontFamily: 'Roboto')),
          textDirection: TextDirection.ltr)
        ..layout();
      text.paint(canvas, Offset(0, y));
    }
    for (final key in ['actual', 'forecast']) {
      final paint = Paint()
        ..color =
            key == 'actual' ? const Color(0xFF1565C0) : const Color(0xFFBF5B16)
        ..strokeWidth = 2;
      Offset? previous;
      Object? version;
      for (var i = 0; i < rows.length; i++) {
        final value = fvChartNumber(rows[i][key]);
        if (value == null) {
          previous = null;
          continue;
        }
        final current = point(i, value);
        if (previous != null &&
            !(binary && key == 'actual') &&
            (key == 'actual' || version == rows[i]['version'])) {
          if (key == 'actual') {
            canvas.drawLine(previous, current, paint);
          } else {
            final delta = current - previous;
            for (double n = 0; n < delta.distance; n += 9) {
              canvas.drawLine(
                  previous + delta * (n / delta.distance),
                  previous +
                      delta *
                          (math.min(n + 5, delta.distance) / delta.distance),
                  paint);
            }
          }
        }
        canvas.drawCircle(current, key == 'forecast' ? 3 : 2, paint);
        previous = current;
        version = rows[i]['version'];
      }
    }
  }

  @override
  bool shouldRepaint(covariant _TimelinePainter old) =>
      old.rows != rows || old.asOf != asOf || old.binary != binary;
}
