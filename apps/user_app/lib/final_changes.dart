import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalChangeCard extends StatelessWidget {
  const FinalChangeCard(this.data, {super.key});
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final rows = fvRows(data['observations']).map(fvMap).toList();
    if (rows.isEmpty) {
      return fvPanel(child: const Text('目前缺少可核對事實，等待資料更新。'));
    }
    final usable = rows.where((r) => r['status'] == 'available').toList();
    const kindOrder = ['operation', 'valuation', 'price', 'event'];
    int rank(Map<String, dynamic> row) =>
        row['status'] == 'available' ? 0 : 1;
    int changeRank(Map<String, dynamic> row) =>
        row['changed'] == true &&
                const {'new', 'strengthened', 'weakened', 'invalidated'}
                    .contains(row['state'])
            ? 0
            : 1;
    int freshness(Map<String, dynamic> row) =>
        DateTime.tryParse(fvText(row['source_available_at']))
            ?.millisecondsSinceEpoch ?? 0;
    int compareRows(Map<String, dynamic> a, Map<String, dynamic> b) {
      final byAvailability = rank(a).compareTo(rank(b));
      if (byAvailability != 0) return byAvailability;
      final byChange = changeRank(a).compareTo(changeRank(b));
      if (byChange != 0) return byChange;
      return freshness(b).compareTo(freshness(a));
    }
    final primary = <Map<String, dynamic>>[];
    for (final kind in kindOrder) {
      final matches = rows.where((r) => r['kind'] == kind).toList()
        ..sort(compareRows);
      if (matches.isNotEmpty) primary.add(matches.first);
    }
    primary.sort((a, b) {
      final byEvidence = compareRows(a, b);
      if (byEvidence != 0) return byEvidence;
      return kindOrder.indexOf(fvText(a['kind']))
          .compareTo(kindOrder.indexOf(fvText(b['kind'])));
    });
    // The next observation and invalidation must describe the same primary
    // evidence as the headline, rather than an unrelated first JSON row.
    final focus = primary.isNotEmpty ? primary.first : rows.first;
    final supports = usable
        .where((r) =>
            r['condition'] == 'positive' && (fvNumber(r['value']) ?? 0) > 0)
        .take(2);
    final questions = usable
        .where((r) =>
            (r['condition'] == 'positive' && (fvNumber(r['value']) ?? 0) < 0) ||
            (r['kind'] == 'event' && (fvNumber(r['value']) ?? 0) >= 75))
        .take(2);
    return fvPanel(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('目前狀態與最新變化',
          style: TextStyle(
              color: fvInk, fontSize: 18, fontWeight: FontWeight.w800)),
      for (final row in primary.take(3)) ...[
        const SizedBox(height: 10),
        Text(
            '${fvText(row['state_label'])}${row['revision'] == true ? ' · 來源修訂' : ''}｜${fvText(row['headline'])}',
            style: const TextStyle(color: fvInk, fontWeight: FontWeight.w700)),
        Text(
            '資料期 ${fvText(row['period'])}${row['status'] == 'available' ? '' : ' · 待更新，保留前次觀察'}',
            style: const TextStyle(color: fvMuted, fontSize: 12)),
        if (row['comparison_value'] != null)
          Text(
              '前次 ${fvText(row['previous_period'])}：${legacy.accountingNumber(row['comparison_value'], decimals: 2)} ${fvText(row['unit'])}',
              style: const TextStyle(color: fvMuted, fontSize: 12)),
      ],
      const SizedBox(height: 10),
      Text(
          '下一觀察：${fvText(focus['next_check'], missing: '下次資料更新後確認')}'),
      Text(
          '失效條件：${fvText(focus['invalidation_condition'], missing: '來源更正或口徑改變時重新確認')}'),
      if (supports.isNotEmpty) ...[
        const SizedBox(height: 8),
        const Text('支持線索（觀察規則）', style: TextStyle(fontWeight: FontWeight.w700)),
        for (final row in supports) Text(fvText(row['headline'])),
      ],
      if (questions.isNotEmpty) ...[
        const SizedBox(height: 8),
        const Text('待確認', style: TextStyle(fontWeight: FontWeight.w700)),
        for (final row in questions) Text(fvText(row['headline'])),
      ],
      Text(
          '截止 ${fvText(data['cutoff_at'])} · 收盤資料日 ${fvText(data['price_date'])}',
          style: const TextStyle(color: fvMuted, fontSize: 12)),
      Text(fvText(data['basis_note']),
          style: const TextStyle(color: fvMuted, fontSize: 12)),
      if (rows.isNotEmpty)
        ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('來源與口徑'),
            children: [
              for (final row in rows)
                ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(fvText(row['headline'])),
                    subtitle: Text(
                        '${fvText(row['period'])} · ${fvText(row['meaning'])}\n${fvRows(row['evidence_refs']).map((e) {
                      final ref = fvMap(e);
                      return '${fvText(ref['source_id'])} · 可得時間 ${fvText(row['source_available_at'])}\n${fvText(ref['location'])}';
                    }).join('\n')}')),
            ]),
    ]));
  }
}
