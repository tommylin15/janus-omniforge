import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_changes.dart';
import 'package:janus_user_app/final_today_v2.dart';
import 'package:janus_user_app/main.dart' as legacy;

class ChangesApi extends legacy.Api {
  ChangesApi() : super('test');
  final calls = <String>[];
  @override
  Future<dynamic> get(String path) async {
    calls.add(path);
    if (path.contains('today-changes')) {
      return {
        'status': 'available',
        'items': [
          {
            'symbol': '2330',
            'state_label': '增強',
            'headline': '月營收 100 元',
            'period': '2026-09-30',
            'cutoff_at': '2026-10-21T09:00:00+08:00',
            'next_check': '下次月營收更新後確認',
          }
        ]
      };
    }
    return <String, dynamic>{};
  }
}

void main() {
  for (final width in [390.0, 1440.0]) {
    testWidgets(
        'fact card readable at $width with large text and source detail',
        (tester) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(MaterialApp(
          home: MediaQuery(
              data: MediaQueryData(
                  size: Size(width, 900),
                  textScaler: const TextScaler.linear(2)),
              child: Scaffold(
                body: SingleChildScrollView(
                    child: FinalChangeCard({
                  'price_date': '2026-10-20',
                  'cutoff_at': '2026-10-21T09:00:00+08:00',
                  'basis_note': '依最近已保存收盤資料',
                  'observations': [
                    {
                      'kind': 'operation',
                      'state_label': '待更新',
                      'status': 'missing',
                      'headline': '同份財報每股盈餘年增率 10 %',
                      'period': '2026-06-30',
                      'next_check': '下次同口徑資料更新後確認',
                      'invalidation_condition': '同口徑數值不再大於零',
                      'evidence_refs': [
                        {
                          'source_id': 'mops',
                          'location': 'iceberg://core.financials_v1'
                        }
                      ],
                    }
                  ],
                })),
              ))));
      await tester.pumpAndSettle();
      expect(find.textContaining('待更新，保留前次觀察'), findsOneWidget);
      expect(find.textContaining('下一觀察：'), findsOneWidget);
      expect(find.textContaining('失效條件：'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('homepage changes precede market and session switch is read only',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = ChangesApi();
    String? selected;
    await tester.pumpWidget(MaterialApp(
        home: FinalTodayPage(api, onOpenStock: (s) => selected = s)));
    await tester.pumpAndSettle();
    final change = find.textContaining('2330 · 增強');
    expect(change, findsOneWidget);
    expect(tester.getTopLeft(change).dy,
        lessThan(tester.getTopLeft(find.text('加權指數')).dy));
    await tester.tap(change);
    expect(selected, '2330');
    await tester.tap(find.text('盤前'));
    await tester.pumpAndSettle();
    expect(api.calls.where((p) => p.contains('today-changes')).length, 2);
    expect(api.calls.last, '/api/v1/me/today-changes?session=premarket');
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
