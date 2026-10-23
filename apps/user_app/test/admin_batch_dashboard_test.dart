import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/admin.dart';

class BatchApi implements AdminApi {
  final writes = <Map<String, dynamic>>[];
  @override
  Future<dynamic> get(String path) async => {
        'controller_fresh': true,
        'items': [
          {
            'name': 'ingestion',
            'title': '收集市場資料',
            'purpose': '取得上市與上櫃行情',
            'cadence': 'daily',
            'enabled': true,
            'paused': false,
            'control_version': 3,
            'can_start': true,
            'can_stop': false,
            'schedule': {
              'hours': [7, 14],
              'minute': 30
            },
            'latest': {
              'status': 'succeeded',
              'start_time': '2026-10-23T00:00:00Z',
              'duration_seconds': 90
            },
          },
          {
            'name': 'monthly-model-review',
            'title': '每月模型有效性檢查',
            'purpose': '尚未啟用',
            'cadence': 'monthly',
            'enabled': false,
            'paused': false,
            'control_version': 0,
            'can_start': false,
            'can_stop': false,
            'latest': null,
            'unavailable_reason': '總控批次尚未實作',
          },
        ],
      };
  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    writes.add({'path': path, ...body});
    return {'message': '請求已保存，尚未代表執行成功'};
  }

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async => body;
  @override
  Future<dynamic> patch(String path, Map<String, dynamic> body) async => body;
}

void main() {
  testWidgets(
      'batch groups show purpose, Taipei time, duration, and versioned manual start',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final api = BatchApi();
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: AdminEffectiveBatches(api))));
    await tester.pumpAndSettle();
    for (final text in ['每日工作', '每週工作', '每月工作']) {
      expect(find.text(text), findsOneWidget);
    }
    expect(find.textContaining('08:00 · 耗時：1.5分鐘'), findsOneWidget);
    await tester.tap(find.text('收集市場資料 · 成功'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('啟動一次').first);
    await tester.pumpAndSettle();
    expect(api.writes, isEmpty);
    await tester.tap(find.widgetWithText(FilledButton, '啟動一次').last);
    await tester.pumpAndSettle();
    expect(
        api.writes.single['path'], '/api/v1/admin/batches/ingestion/actions');
    expect(api.writes.single['expected_version'], 3);
    expect(api.writes.single['action'], 'start');
  });

  testWidgets(
      'unimplemented monthly batch explains why start and stop are disabled on a phone',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: AdminEffectiveBatches(BatchApi()))));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('每月模型有效性檢查 · 尚未啟用'), 180);
    await tester.tap(find.text('每月模型有效性檢查 · 尚未啟用'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('總控批次尚未實作'), 180);
    expect(find.text('總控批次尚未實作'), findsOneWidget);
    final start = tester
        .widget<FilledButton>(find.widgetWithText(FilledButton, '啟動一次').last);
    expect(start.onPressed, isNull);
    expect(tester.takeException(), isNull);
  });
}
