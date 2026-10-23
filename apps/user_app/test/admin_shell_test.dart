import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/admin.dart';
import 'package:janus_user_app/main.dart';

class _ShellApi implements AdminApi {
  @override
  Future<dynamic> get(String path) async {
    if (path.startsWith('/api/v1/admin/batches'))
      return {'items': [], 'definitions': []};
    if (path == '/api/v1/admin/executions?limit=50') {
      return {'items': <dynamic>[]};
    }
    if (path == '/api/v1/admin/source-health?limit=200&active_only=true') {
      return {
        'items': [
          {
            'source_id': 'twse',
            'dataset_id': 'ohlcv',
            'last_state': 'success',
          }
        ],
      };
    }
    if (path == '/api/v1/admin/mart-reports?limit=50') {
      return {'items': <dynamic>[]};
    }
    return {'items': <dynamic>[]};
  }

  @override
  Future<dynamic> patch(String path, Map<String, dynamic> body) async => body;

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    if (path == '/api/v1/admin/gcs-storage/inspect') {
      return <String, dynamic>{
        'status': 'KNOWN_BUCKETS_COMPLETE',
        'observed_at_utc': '2026-10-20T00:00:00Z',
        'totals': <String, dynamic>{
          'current_bytes': 250,
          'current_objects': 2,
          'noncurrent_bytes': 0,
          'soft_deleted_bytes': 0
        },
        'buckets': <Map<String, dynamic>>[
          {
            'role': 'stage',
            'status': 'OBSERVED',
            'current_bytes': 100,
            'current_objects': 1,
            'noncurrent_bytes': 0,
            'soft_deleted_bytes': 0,
            'possible_same_md5_extra_bytes': 0
          },
          {
            'role': 'core',
            'status': 'OBSERVED',
            'current_bytes': 150,
            'current_objects': 1,
            'noncurrent_bytes': 0,
            'soft_deleted_bytes': 0
          },
        ],
      };
    }
    return body;
  }

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async => body;
}

void main() {
  test('admin workspace requires an explicit admin route or build mode', () {
    expect(
      adminWorkspaceRequested(Uri.parse('https://example.test/app/admin')),
      isTrue,
    );
    expect(
      adminWorkspaceRequested(Uri.parse('https://example.test/app')),
      isFalse,
    );
    expect(
      adminWorkspaceRequested(
        Uri.parse('https://example.test/app'),
        'admin',
      ),
      isTrue,
    );
  });

  testWidgets('admin shell uses Chinese desktop navigation', (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 900));
    await tester.pumpWidget(
      MaterialApp(
        home: AdminWorkspace(
          api: _ShellApi(),
          email: 'admin@example.com',
          onTheme: (_) {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.text('資料營運中心 · 總覽'), findsOneWidget);
    for (final label in [
      '總覽',
      '批次',
      '資料品質',
      '系統設定',
    ]) {
      expect(find.text(label), findsWidgets);
    }
    expect(tester.takeException(), isNull);
  });

  testWidgets('admin shell switches to a mobile navigation drawer',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(390, 844));
    await tester.pumpWidget(
      MaterialApp(
        home: AdminWorkspace(
          api: _ShellApi(),
          email: 'admin@example.com',
          onTheme: (_) {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(NavigationRail), findsNothing);
    expect(find.byIcon(Icons.menu), findsOneWidget);
    await tester.tap(find.byIcon(Icons.menu));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationDrawer), findsOneWidget);
    expect(find.text('資料營運中心'), findsWidgets);
    expect(find.text('總覽'), findsWidgets);
    expect(find.text('批次'), findsWidgets);
    expect(find.text('資料品質'), findsWidgets);
    expect(find.text('系統設定'), findsWidgets);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'Admin Storage has one-click readonly GCS inventory and labels MD5 as potential only',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 900));
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: AdminGovernancePage(_ShellApi(), section: 'storage'))));
    await tester.pumpAndSettle();
    final button = find.byKey(const ValueKey('admin-gcs-inventory-button'));
    expect(button, findsOneWidget);
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(find.textContaining('六桶盤點完成'), findsOneWidget);
    expect(find.textContaining('六桶合計：0.00 MB'), findsOneWidget);
    expect(find.textContaining('MD5 疑似重複 0.00 MB（不可直接刪除）'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('four pages retain sections without loading hidden operations',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 900));
    await tester.pumpWidget(MaterialApp(
        home: AdminWorkspace(
            api: _ShellApi(), email: 'admin@example.com', onTheme: (_) {})));
    await tester.pumpAndSettle();
    Future<void> navigate(String label) async {
      await tester.tap(find.descendant(
          of: find.byType(NavigationRail), matching: find.text(label)));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    }

    await navigate('資料品質');
    expect(find.textContaining('尚無持久化 Data Readiness Ledger'), findsOneWidget);
    await navigate('系統設定');
    await navigate('批次');
    await navigate('總覽');
    expect(find.byType(NavigationRail), findsOneWidget);
    expect(
        (tester.widget(find.byType(NavigationRail)) as NavigationRail)
            .destinations,
        hasLength(4));
  });
  test('Admin GCS MB presentation groups amounts without fabricating nulls',
      () {
    expect(formatAdminStorageMb(785411117), '785.41 MB');
    expect(formatAdminStorageMb(1234567890), '1,234.57 MB');
    expect(formatAdminStorageMb(0), '0.00 MB');
    expect(formatAdminStorageMb(null), '未知');
    expect(formatAdminStorageCount(1234567), '1,234,567');
    expect(formatAdminStorageCount(null), '未知');
    expect(
        adminStorageTotalBytes({
          'current_bytes': 782661499,
          'noncurrent_bytes': 2749618,
          'soft_deleted_bytes': 0
        }),
        785411117);
    expect(
        adminStorageTotalBytes({
          'current_bytes': 10,
          'noncurrent_bytes': null,
          'soft_deleted_bytes': 0
        }),
        isNull);
  });
}
