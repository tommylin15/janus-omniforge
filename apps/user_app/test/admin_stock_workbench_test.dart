import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/admin.dart';

class _WorkbenchApi implements AdminApi {
  final reads = <String>[];
  final writes = <Map<String, dynamic>>[];

  @override
  Future<dynamic> get(String path) async {
    reads.add(path);
    if (path == '/api/v1/admin/stocks?q=&limit=10') {
      return {
        'items': [
          {'symbol': '2330', 'name': '台積電', 'market': 'TWSE', 'enabled': true},
          {'symbol': '2454', 'name': '聯發科', 'market': 'TWSE', 'enabled': true},
        ],
      };
    }
    if (path == '/api/v1/admin/stocks?q=%E5%8F%B0%E7%A9%8D&limit=10') {
      return {
        'items': [
          {'symbol': '2330', 'name': '台積電', 'market': 'TWSE', 'enabled': true},
        ],
      };
    }
    if (path == '/api/v1/admin/stocks/2330/status') {
      return {
        'items': [
          {
            'dataset_id': 'ohlcv',
            'status': 'available',
            'row_count': 20,
            'received_symbols': 1,
            'requested_symbols': 1,
            'dq_warning_count': 0,
            'latest_date': '2026-09-29',
            'source_ids': ['twse'],
            'execution_ids': ['exec-old'],
            'snapshot_ids': ['snap-old'],
            'provenance_ids': ['prov-old'],
            'freshness': 'fresh',
            'updated_at': '2026-09-29T10:00:00+00:00',
          },
          {
            'dataset_id': 'valuation',
            'status': 'missing',
            'row_count': 0,
            'received_symbols': 0,
            'requested_symbols': 1,
            'dq_warning_count': 0,
            'latest_date': null,
            'source_ids': <String>[],
            'execution_ids': <String>[],
            'snapshot_ids': <String>[],
            'provenance_ids': <String>[],
          },
        ],
      };
    }
    if (path == '/api/v1/admin/mart-reports?scope_type=symbol&scope_id=2330&limit=50') {
      return {
        'items': [
          {
            'analysis_as_of': '2026-09-20',
            'analysis_outcome': 'complete',
            'prompt_version': 'v1',
            'publication_status': 'published',
          },
        ],
      };
    }
    if (path == '/api/v1/admin/source-catalog?limit=200') {
      return {
        'items': [
          {
            'config_id': 'valuation',
            'dataset_id': 'valuation',
            'source_ids': ['twse'],
            'enabled': true,
            'collection_enabled': true,
            'authorization_status': 'official',
          },
          {
            'config_id': 'valuation-blocked',
            'dataset_id': 'valuation',
            'source_ids': ['candidate-source'],
            'enabled': true,
            'collection_enabled': true,
            'authorization_status': 'blocked',
          },
        ],
      };
    }
    return {'items': <dynamic>[]};
  }

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    writes.add({'path': path, ...body});
    return body;
  }

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async => body;

  @override
  Future<dynamic> patch(String path, Map<String, dynamic> body) async => body;
}

void main() {
  testWidgets('stock workbench searches by Chinese name', (tester) async {
    final api = _WorkbenchApi();
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: AdminStockWorkbench(api))),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, '台積');
    await tester.tap(find.text('搜尋'));
    await tester.pumpAndSettle();

    expect(
      api.reads,
      contains('/api/v1/admin/stocks?q=%E5%8F%B0%E7%A9%8D&limit=10'),
    );
    expect(find.textContaining('2330 台積電'), findsOneWidget);
  });

  testWidgets('stock workbench exposes bounded gap repair and read-only lineage',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 1000));
    final api = _WorkbenchApi();
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: AdminStockWorkbench(api))),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.textContaining('2330 台積電'));
    await tester.pumpAndSettle();

    expect(find.text('資料健康'), findsOneWidget);
    expect(find.textContaining('覆蓋 0/1 · 缺口 1'), findsOneWidget);
    expect(find.text('重新分析'), findsNothing);
    expect(find.text('Specialist／CEO 分析尚未啟用'), findsOneWidget);

    final repair = find.widgetWithText(FilledButton, '修復');
    expect(repair, findsOneWidget);
    await tester.tap(repair);
    await tester.pumpAndSettle();

    expect(api.writes, hasLength(1));
    expect(api.writes.single['path'], '/api/v1/admin/executions/collection');
    expect(api.writes.single['config_id'], 'valuation');
    expect(api.writes.single['symbols'], ['2330']);
    expect(
      api.writes.any((write) => write['config_id'] == 'valuation-blocked'),
      isFalse,
    );

    await tester.scrollUntilVisible(
      find.text('技術追蹤（唯讀）'),
      200,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.tap(find.text('技術追蹤（唯讀）'));
    await tester.pumpAndSettle();
    expect(find.textContaining('exec-old'), findsOneWidget);
    expect(find.textContaining('snap-old'), findsOneWidget);
    expect(find.textContaining('prov-old'), findsOneWidget);
    expect(find.textContaining('舊 execution／snapshot 保持不可變更'), findsOneWidget);
  });
}
