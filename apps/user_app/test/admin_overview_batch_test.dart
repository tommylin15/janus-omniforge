import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/admin.dart';

class _OperationsApi implements AdminApi {
  final posts = <String>[];

  @override
  Future<dynamic> get(String path) async {
    if (path == '/api/v1/admin/executions?limit=50') {
      return {
        'items': [
          {
            'execution_id': 'failed-1',
            'trace_id': 'trace-1',
            'config_id': 'ohlcv',
            'trigger_type': 'collection',
            'status': 'partial',
            'requested_at': '2026-09-29T10:00:00+00:00',
          },
          {
            'execution_id': 'success-1',
            'trace_id': 'trace-2',
            'config_id': 'valuation',
            'trigger_type': 'collection',
            'status': 'succeeded',
            'requested_at': '2026-09-29T09:00:00+00:00',
          },
        ],
      };
    }
    if (path == '/api/v1/admin/source-health?limit=200') {
      return {
        'items': [
          {
            'source_id': 'twse',
            'dataset_id': 'ohlcv',
            'last_state': 'unavailable',
            'last_fetched_at': '2026-09-29T09:55:00+00:00',
          },
          {
            'source_id': 'mops',
            'dataset_id': 'financials',
            'last_state': 'success',
          },
        ],
      };
    }
    if (path == '/api/v1/admin/mart-reports?limit=50') {
      return {
        'items': [
          {
            'execution_id': 'mart-1',
            'scope_type': 'symbol',
            'scope_id': '2330',
            'analysis_as_of': '2026-09-29',
            'analysis_outcome': 'review_required',
            'publication_status': 'blocked',
          },
        ],
      };
    }
    if (path == '/api/v1/admin/executions/failed-1') {
      return {
        'execution_id': 'failed-1',
        'trace_id': 'trace-1',
        'config_id': 'ohlcv',
        'trigger_type': 'collection',
        'status': 'partial',
        'items': [
          {
            'item_key': 'ohlcv:TWSE:2330',
            'source_id': 'twse',
            'dataset_id': 'ohlcv',
            'state': 'failed',
            'retry_count': 1,
            'safe_message': '來源暫時無法使用',
            'retry_classification': 'retryable',
          },
          {
            'item_key': 'ohlcv:TWSE:2454',
            'source_id': 'twse',
            'dataset_id': 'ohlcv',
            'state': 'failed',
            'retry_count': 0,
            'safe_message': '來源授權失敗',
            'retry_classification': 'non_retryable',
          },
        ],
        'lineage': {
          'trace_id': 'trace-1',
          'executions': [
            {
              'execution_id': 'failed-1',
              'status': 'partial',
              'requested_at': '2026-09-29T10:00:00+00:00',
            },
            {
              'execution_id': 'retry-1',
              'status': 'queued',
              'requested_at': '2026-09-29T10:05:00+00:00',
            },
          ],
        },
      };
    }
    return {'items': <dynamic>[]};
  }

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    posts.add(path);
    return {'status': 'queued'};
  }

  @override
  Future<dynamic> patch(String path, Map<String, dynamic> body) async => body;

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async => body;
}

void main() {
  testWidgets('overview is actionable-issues-first and hides healthy execution noise',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 1200));
    final api = _OperationsApi();
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: AdminOverviewPage(api))),
    );
    await tester.pumpAndSettle();

    expect(find.text('優先處理'), findsOneWidget);
    expect(find.textContaining('ohlcv · 部分完成'), findsOneWidget);
    expect(find.textContaining('twse · ohlcv'), findsOneWidget);
    expect(find.textContaining('2330 · 已阻擋'), findsOneWidget);
    expect(find.textContaining('valuation ·'), findsNothing);
    expect(find.text('正常 execution 不會佔用此區塊'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('overview opens lineage and retries only retryable failed item',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 1200));
    final api = _OperationsApi();
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: AdminOverviewPage(api))),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('查看與處理'));
    await tester.pumpAndSettle();

    expect(find.text('追蹤 ID trace-1'), findsOneWidget);
    expect(find.text('不可重試'), findsOneWidget);
    expect(find.text('重試'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('retry-1'), 200,
        scrollable: find.byType(Scrollable).last);
    expect(find.text('retry-1'), findsOneWidget);

    await tester.tap(find.text('重試'));
    await tester.pumpAndSettle();

    expect(
      api.posts,
      contains(
        '/api/v1/admin/executions/failed-1/items/ohlcv%3ATWSE%3A2330/retry',
      ),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('batch classifies partial separately from succeeded and keeps details operable',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 1200));
    final api = _OperationsApi();
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: AdminBatchPage(api))),
    );
    await tester.pumpAndSettle();

    expect(find.text('需要處理 1'), findsOneWidget);
    expect(find.text('已完成 1'), findsOneWidget);
    expect(find.textContaining('部分完成'), findsWidgets);
    expect(find.textContaining('成功'), findsWidgets);

    await tester.tap(find.text('查看').first);
    await tester.pumpAndSettle();
    expect(find.text('執行追蹤'), findsOneWidget);
    expect(find.text('重試'), findsOneWidget);
    expect(find.text('不可重試'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
