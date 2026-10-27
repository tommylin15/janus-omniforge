import 'package:flutter/material.dart';

import 'final_charts.dart' show fvChartNumber;
import 'final_visual_common.dart';
import 'risk_signal_ui.dart';

const stockRoleNames = {
  'quant': '股價走勢', 'fundamental': '公司營運',
  'valuation': '價格評價', 'risk': '波動風險',
};

/// Equal units share a scale; missing values never become zero-length facts.
class StockMetricBars extends StatelessWidget {
  const StockMetricBars(this.values, {super.key, this.unit = '%'});
  final Map<String, double?> values;
  final String unit;

  @override
  Widget build(BuildContext context) {
    final finite = values.values.whereType<double>().where((v) => v.isFinite);
    final scale = finite.fold<double>(0, (m, v) => v.abs() > m ? v.abs() : m);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final entry in values.entries) Builder(builder: (context) {
        final value = entry.value;
        final valid = value != null && value.isFinite;
        final fraction = valid && scale > 0 ? value.abs() / scale : 0.0;
        final label = valid
            ? '${value > 0 ? '+' : ''}${value.toStringAsFixed(1)}$unit'
            : '資料不足';
        return Padding(padding: const EdgeInsets.symmetric(vertical: 6),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${entry.key}：$label'),
            if (valid) Semantics(label: '${entry.key} $label，中央為零',
              child: SizedBox(height: 16, child: Row(children: [
                Expanded(child: Align(alignment: Alignment.centerRight,
                  child: FractionallySizedBox(widthFactor: value < 0 ? fraction : 0,
                    child: Container(height: 10, color: fvLoss)))),
                Container(width: 1, height: 16, color: fvMuted),
                Expanded(child: Align(alignment: Alignment.centerLeft,
                  child: FractionallySizedBox(widthFactor: value > 0 ? fraction : 0,
                    child: Container(height: 10, color: fvGain)))),
              ]))),
          ]));
      }),
    ]);
  }
}

class StockValuationBand extends StatelessWidget {
  const StockValuationBand(this.reference, {super.key});
  final Map<String, dynamic> reference;

  @override
  Widget build(BuildContext context) {
    final low = fvChartNumber(reference['lower']);
    final mid = fvChartNumber(reference['mid']);
    final high = fvChartNumber(reference['upper']);
    final available = reference['status'] == 'available' &&
        DateTime.tryParse(fvText(reference['as_of'])) != null && low != null &&
        mid != null && high != null && low > 0 && low <= mid && mid <= high;
    if (!available) return const Text('參考價帶資料不足，暫時不能判斷價格位置。');
    final position = high == low ? 0.5 : (mid - low) / (high - low);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('估值參考價帶（元／股）'),
      const SizedBox(height: 8),
      Semantics(label: '下緣 $low，中位 $mid，上緣 $high 元每股',
        child: SizedBox(height: 20, child: Stack(children: [
          Positioned(left: 0, right: 0, top: 6,
            child: Container(height: 8, color: fvSoft)),
          Align(alignment: Alignment(position * 2 - 1, 0),
            child: Container(width: 4, height: 20, color: fvTeal)),
        ]))),
      Wrap(spacing: 16, runSpacing: 4, children: [
        Text('下緣 ${low.toStringAsFixed(2)}'),
        Text('中位 ${mid.toStringAsFixed(2)}'),
        Text('上緣 ${high.toStringAsFixed(2)}'),
      ]),
      const Text('這是估值假設的參考範圍，不是目標價，也不保證股價會到達。',
        style: TextStyle(color: fvMuted, fontSize: 12)),
    ]);
  }
}

class StockFactsPanel extends StatelessWidget {
  const StockFactsPanel(this.baseline, {super.key});
  final Map<String, dynamic> baseline;

  @override
  Widget build(BuildContext context) {
    final roles = {for (final row in fvRows(baseline['specialists']))
      fvMap(row)['role']: fvMap(row)};
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      fvSectionTitle(context, '用四個角度看懂這家公司'),
      const Text('先看已發生的數字，再看預測；各面向不能加總成買賣分數。',
        style: TextStyle(color: fvMuted, fontSize: 12)),
      for (final role in const ['quant', 'fundamental', 'valuation'])
        Padding(padding: const EdgeInsets.only(top: 10), child: Builder(builder: (context) {
          final item = roles[role] ?? <String, dynamic>{};
          final dated = DateTime.tryParse(fvText(item['analysis_as_of'])) != null;
          final metrics = item['status'] == 'blocked' || item['baseline_status'] != 'available' || !dated
              ? <String, dynamic>{} : fvMap(item['metrics']);
          return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(stockRoleNames[role]!, style: const TextStyle(fontWeight: FontWeight.w800)),
            Text('資料日 ${fvText(item['analysis_as_of'])}'
                '${baseline['freshness'] == 'stale' ? ' · 資料過期，僅供歷史參考' : ''}',
              style: const TextStyle(color: fvMuted, fontSize: 12)),
            if (role == 'quant') ...[
              StockMetricBars({for (final days in [5, 20, 60])
                '近 $days 個交易日': fvChartNumber(metrics['return_${days}d_percent'])}),
              const Text('從零線向右是上漲、向左是下跌。這是過去表現，不代表未來漲跌。',
                style: TextStyle(color: fvMuted, fontSize: 12)),
            ] else if (role == 'fundamental') ...[
              StockMetricBars({
                '營收比較期變化': fvChartNumber(metrics['revenue_trend_percent']),
                '每股盈餘比較期變化': fvChartNumber(metrics['eps_trend_percent']),
              }),
              const Text('營收是公司做了多少生意；每股盈餘（EPS）是每股分攤的獲利。比較期依原始報表，不一定是年增率。',
                style: TextStyle(color: fvMuted, fontSize: 12)),
            ] else ...[
              for (final metric in const {'pe_ratio': '本益比（股價／每股獲利）',
                  'pb_ratio': '股價淨值比（股價／每股淨值）'}.entries)
                Padding(padding: const EdgeInsets.only(top: 8), child: Text(
                  '${metric.value}：${fvChartNumber(metrics[metric.key]) == null ? '資料不足' : '${fvChartNumber(metrics[metric.key])!.toStringAsFixed(2)} 倍'}')),
              const Text('倍數表示價格相對獲利或淨值的高低；不能只因倍數低就判定便宜。',
                style: TextStyle(color: fvMuted, fontSize: 12)),
              const SizedBox(height: 10),
              StockValuationBand(fvMap(baseline['valuation_reference'])),
              Text('估值資料日 ${fvText(fvMap(baseline['valuation_reference'])['as_of'])}',
                style: const TextStyle(color: fvMuted, fontSize: 12)),
            ],
            if (item.isNotEmpty) ExpansionTile(title: const Text('查看數字口徑'), children: [
              Text(fvText(item['plain_language'], missing: '來源未提供補充說明')),
            ]),
          ]));
        })),
      RiskSignalCard(specialist: {
        ...?roles['risk'],
        'seq08_native_model': fvMap(fvMap(baseline['four_model_serving'])['risk']),
      }, freshness: fvText(baseline['freshness'], missing: 'unavailable')),
    ]);
  }
}

String stockEventReadingTip(Map<String, dynamic> row) {
  final text = '${row['title'] ?? ''} ${row['event_type'] ?? ''}';
  if (RegExp('除權|除息|股利|dividend', caseSensitive: false).hasMatch(text)) {
    return '閱讀提示：留意除權息日期、每股金額與領取條件；配息不等於額外獲利。';
  }
  if (RegExp('營收|財報|盈餘|revenue|earnings', caseSensitive: false).hasMatch(text)) {
    return '閱讀提示：對照營收與獲利圖，確認報表期間及比較基期。';
  }
  if (RegExp('法說|investor', caseSensitive: false).hasMatch(text)) {
    return '閱讀提示：區分已實現業績與公司展望，後續用財報確認。';
  }
  return '閱讀提示：先確認公告內容與生效日；公告本身不代表利多或利空。';
}
