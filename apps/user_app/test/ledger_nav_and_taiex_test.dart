import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/main.dart' as legacy;

class _NavAndTaiexFakeApi extends legacy.Api {
  _NavAndTaiexFakeApi(this.values) : super('test');

  final Map<String, dynamic> values;

  @override
  Future<dynamic> get(String path) async => values[path] ?? const <dynamic>[];

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async => body;
}

Map<String, dynamic> _marketHomePayload() => {
      'sections': {
        'taiex': {
          'status': 'available',
          'as_of': '2026-11-18',
          'data': {
            'close': 23456.78,
            'quote_state': 'intraday',
            'quote_at': '2026-11-18T02:15:30Z',
            'quote_previous_close': 23300.00,
            'history_points': [
              {
                'date': '2026-11-17',
                'value': 23300.00,
                'source_id': 'twse',
                'provenance_id': 'p1',
              },
            ],
            'intraday_points': [
              {'date': '2026-11-18T01:00:00Z', 'value': 23400.00},
              {'date': '2026-11-18T02:15:30Z', 'value': 23456.78},
            ],
          },
        },
      },
    };

Map<String, dynamic> _baseApiValues() => {
      '/api/v1/me/portfolio/snapshot': {
        'ledger_version': 5,
        'session': 'regular',
        'positions': const <dynamic>[],
        'items': const <dynamic>[],
      },
      '/api/v1/me/portfolio/quotes': {
        'session': 'regular',
        'positions': const <dynamic>[],
        'items': const <dynamic>[],
      },
      '/api/v1/me/personal-strategy/access': {'allowed': false},
      '/api/v1/public/market-home': _marketHomePayload(),
    };

void main() {
  testWidgets('FinalWorkspace puts 持股／記帳 leftmost and selects it by default',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = _NavAndTaiexFakeApi(_baseApiValues());
    await tester.pumpWidget(
      MaterialApp(
        home: FinalWorkspace(
          api: api,
          email: 'owner@example.com',
          onTheme: (_) {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    final navBar = tester.widget<NavigationBar>(find.byType(NavigationBar));
    expect(navBar.selectedIndex, 0);
    expect(
      (navBar.destinations.first as NavigationDestination).label,
      '持股／記帳',
    );
    expect(
      (navBar.destinations[1] as NavigationDestination).label,
      '今日',
    );
    expect(api.usage.feature, 'journal');
    expect(find.byKey(const Key('final-ledger-scroll')), findsOneWidget);
  });

  testWidgets('FinalWorkspace wide layout puts 持股／記帳 first in NavigationRail',
      (tester) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = _NavAndTaiexFakeApi(_baseApiValues());
    await tester.pumpWidget(
      MaterialApp(
        home: FinalWorkspace(
          api: api,
          email: 'owner@example.com',
          onTheme: (_) {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    final rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.selectedIndex, 0);
    expect((rail.destinations.first.label as Text).data, '持股／記帳');
  });

  testWidgets('FinalLedgerPage displays TAIEX card on 持股 tab',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = _NavAndTaiexFakeApi(_baseApiValues());
    await tester.pumpWidget(
      MaterialApp(
        home: FinalLedgerPage(
          api,
          now: () => DateTime.utc(2026, 11, 18, 2, 16),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('ledger-market-summary')), findsOneWidget);
    expect(find.byKey(const Key('ledger-market-index-value')), findsOneWidget);
    expect(find.text('23,456.78'), findsOneWidget);
    expect(find.text('+156.78 點'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
