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
    if (path == '/api/v1/admin/source-health?limit=200') {
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
  Future<dynamic> post(String path, Map<String, dynamic> body) async => body;

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
}
