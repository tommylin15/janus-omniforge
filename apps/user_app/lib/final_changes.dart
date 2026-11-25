import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalChangeCard extends StatelessWidget {
  const FinalChangeCard(this.data, {super.key});
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final v2 = fvMap(data['insight_v2']);
    if (v2['schema_version'] == 'insight.v2') {
      return _InsightV2Card(v2: v2, parentData: data);
    }
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

class _InsightV2Card extends StatelessWidget {
  const _InsightV2Card({required this.v2, required this.parentData});

  final Map<String, dynamic> v2;
  final Map<String, dynamic> parentData;

  (String, Color, Color) _reviewBadge(String status) => switch (status) {
        'REVIEW' => ('REVIEW · 建議優先人工覆核', const Color(0xFFB3261E), const Color(0xFFFFECEA)),
        'WARN' => ('WARN · 異常提醒', const Color(0xFF8A5300), const Color(0xFFFFF4DE)),
        _ => ('OK · 確定性覆核正常', fvTeal, fvSoft),
      };

  void _showEvidenceSheet(BuildContext context, Map<String, dynamic> ref) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(18),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                fvText(ref['label'], missing: '證據來源明細'),
                style: const TextStyle(color: fvInk, fontSize: 16, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text('證據 ID：${fvText(ref['evidence_id'])}'),
              Text('資料來源：${fvText(ref['source_name'])}'),
              Text('資料基準日：${fvText(ref['as_of'])}'),
              Text('驗證數值／摘要：${fvText(ref['display_value'])}'),
              Text('分類導向：${fvText(ref['deep_link'])}', style: const TextStyle(color: fvMuted, fontSize: 12)),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('關閉')),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final reviewStatus = fvText(v2['review_status'], missing: 'OK');
    final (badgeLabel, badgeFg, badgeBg) = _reviewBadge(reviewStatus);
    final meta = fvMap(v2['generation_meta']);
    final modeText = meta['mode'] == 'ai_synthesis' ? 'AI 結構化摘要' : '確定性事實摘要';
    final s30 = fvMap(v2['summary_30s']);
    final primary = fvRows(v2['primary_insights']).map(fvMap).toList();
    final secondary = fvRows(v2['secondary_insights']).map(fvMap).toList();
    final moreCount = fvInt(v2['more_count']);

    return fvPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 6,
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              const Text(
                '30 秒個股變化與覆核',
                style: TextStyle(color: fvInk, fontSize: 18, fontWeight: FontWeight.w800),
              ),
              Container(
                key: const Key('insight-v2-review-badge'),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(color: badgeBg, borderRadius: BorderRadius.circular(12)),
                child: Text(
                  badgeLabel,
                  style: TextStyle(color: badgeFg, fontSize: 12, fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            '$modeText · 基準日 ${fvText(v2['as_of_date'])} · 價格日 ${fvText(v2['price_as_of_date'])}',
            style: const TextStyle(color: fvMuted, fontSize: 12),
          ),
          const SizedBox(height: 10),
          Container(
            key: const Key('insight-v2-summary-30s'),
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: fvPastelDecoration(tone: FvCardTone.mint, radius: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('現況：${fvText(s30['current_state'])}', style: const TextStyle(color: fvInk, fontWeight: FontWeight.w700)),
                const SizedBox(height: 3),
                Text('核心變化：${fvText(s30['key_delta'])}', style: const TextStyle(color: fvInk, fontSize: 13)),
                const SizedBox(height: 3),
                Text('重點觀察：${fvText(s30['top_watch'])}', style: const TextStyle(color: fvMuted, fontSize: 12)),
              ],
            ),
          ),
          for (final item in primary) ...[
            const SizedBox(height: 12),
            Text(
              '${fvText(item['state'])} · ${fvText(item['headline'])}',
              style: const TextStyle(color: fvInk, fontSize: 15, fontWeight: FontWeight.w800),
            ),
            if (fvText(item['meaning'], missing: '').isNotEmpty) ...[
              const SizedBox(height: 3),
              Text(fvText(item['meaning']), style: const TextStyle(color: fvInk, fontSize: 13)),
            ],
            const SizedBox(height: 4),
            Text('下步觀察：${fvText(item['next_check'])}', style: const TextStyle(color: fvMuted, fontSize: 12)),
            Text('失效條件：${fvText(item['invalidation_condition'])}', style: const TextStyle(color: fvMuted, fontSize: 12)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final rawRef in fvRows(item['evidence_refs']))
                  Builder(builder: (context) {
                    final ref = fvMap(rawRef);
                    final eid = fvText(ref['evidence_id']);
                    return ActionChip(
                      key: Key('evidence-chip-$eid'),
                      avatar: const Icon(Icons.fact_check_outlined, size: 15, color: fvTeal),
                      label: Text('${fvText(ref['source_name'])} · ${fvText(ref['display_value'])}'),
                      onPressed: () => _showEvidenceSheet(context, ref),
                    );
                  }),
              ],
            ),
          ],
          if (secondary.isNotEmpty) ...[
            const SizedBox(height: 8),
            ExpansionTile(
              key: const Key('insight-v2-more-tile'),
              tilePadding: EdgeInsets.zero,
              title: Text('查看更多 ($moreCount)'),
              children: [
                for (final sec in secondary)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(fvText(fvMap(sec)['headline'], missing: '補充事實')),
                    subtitle: Text(fvText(fvMap(sec)['meaning'], missing: fvText(fvMap(sec)['period']))),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
