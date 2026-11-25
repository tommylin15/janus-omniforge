import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_changes.dart';

Map<String, dynamic> _sampleInsightV2Payload() => {
      'symbol': '2330',
      'session': 'postmarket',
      'observations': const <dynamic>[],
      'insight_v2': {
        'schema_version': 'insight.v2',
        'canonical_symbol': '2330',
        'as_of_date': '2026-11-25',
        'price_as_of_date': '2026-11-25',
        'review_status': 'REVIEW',
        'triggered_rules': const ['T4_MOPS_GOVERNANCE_EVENT'],
        'generation_meta': {
          'mode': 'ai_synthesis',
          'model_id': 'gemini-hydrogen',
          'prompt_version': 'v2.1.0',
          'facts_events_hash': 'abcdef1234567890',
          'generated_at': '2026-11-25T08:00:00Z',
          'source_status': 'available',
          'quality_gate': {'status': 'PASS', 'error_count': 0, 'warning_count': 0},
        },
        'summary_30s': {
          'current_state': '公告列為處置股票（分盤交易）',
          'key_delta': '經櫃買／證交所公告交易處置措施',
          'top_watch': '關注處置期間流動性與月營收公告',
        },
        'primary_insights': [
          {
            'insight_id': 'ins_2330_20261125_0_123456',
            'previous_id': null,
            'statement_type': 'confirmed_fact',
            'category': 'event',
            'state': 'new',
            'rank_reason': 'material_event',
            'headline': 'T4 處置交易公告',
            'meaning': '重大治理或交易管制公告，建議優先人工覆核。',
            'next_check': '確認處置結束日期與成交量變化',
            'invalidation_condition': '處置期間屆滿並恢復正常撮合',
            'evidence_refs': [
              {
                'evidence_id': 'evt_mops_1',
                'source_name': 'MOPS',
                'as_of': '2026-11-25',
                'label': '處置股票重大訊息',
                'display_value': '分盤交易 10 日',
                'deep_link': '/stock/2330?tab=event',
              }
            ],
          }
        ],
        'secondary_insights': [
          {'headline': '還原收盤價 1,050.0 元', 'meaning': '近期量價平穩'}
        ],
        'more_count': 1,
      },
    };

void main() {
  testWidgets('FinalChangeCard renders insight_v2, evidence bottom sheet, and secondary expansion without overflow at 390px/200%',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(2.0)),
        child: MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: FinalChangeCard(_sampleInsightV2Payload()),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('insight-v2-review-badge')), findsOneWidget);
    expect(find.textContaining('REVIEW · 建議優先人工覆核'), findsOneWidget);
    expect(find.byKey(const Key('insight-v2-summary-30s')), findsOneWidget);
    expect(find.textContaining('T4 處置交易公告'), findsOneWidget);

    final chip = find.byKey(const Key('evidence-chip-evt_mops_1'));
    await tester.ensureVisible(chip);
    await tester.pumpAndSettle();
    await tester.tap(chip);
    await tester.pumpAndSettle();
    expect(find.textContaining('證據 ID：evt_mops_1'), findsOneWidget);
    await tester.tap(find.text('關閉'));
    await tester.pumpAndSettle();

    final moreTile = find.byKey(const Key('insight-v2-more-tile'));
    await tester.ensureVisible(moreTile);
    await tester.pumpAndSettle();
    await tester.tap(moreTile);
    await tester.pumpAndSettle();
    expect(find.textContaining('還原收盤價 1,050.0 元'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('FinalChangeCard falls back cleanly to legacy observations when insight_v2 is absent',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: FinalChangeCard({
            'symbol': '2330',
            'session': 'postmarket',
            'observations': <dynamic>[],
          }),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('目前缺少可核對事實，等待資料更新。'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
