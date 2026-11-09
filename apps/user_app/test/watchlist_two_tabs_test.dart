import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_watchlist.dart';
import 'package:janus_user_app/main.dart' as legacy;

class WatchTwoTabsApi extends legacy.Api {
  WatchTwoTabsApi() : super('test');
  final calls = <String>[];

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async =>
      {'status': 'unavailable'};

  @override
  Future<dynamic> get(String path) async {
    calls.add(path);
    if (path == '/api/v1/me/watchlist') return [
      {
        'symbol': '2330', 'stock_name': '台積電', 'tier': 'A',
        'version': 4, 'sort_order': 1, 'held': true,
        'market_price': '1000', 'price_status': 'available',
        'quote_state': 'intraday', 'change': '10',
        'previous_close': '990', 'change_percent': '0.0101',
        'price_date': '2026-11-09', 'tier_confirmed': true,
        'target_price': '1100', 'in_market': true,
      },
      {
        'symbol': '2327', 'stock_name': '國巨', 'tier': 'B',
        'version': 4, 'sort_order': 2, 'held': false,
        'market_price': '411', 'price_status': 'stale',
        'quote_state': 'stale', 'price_date': '2026-11-08',
        'tier_confirmed': true, 'in_market': false,
      },
    ];
    if (path.startsWith('/api/v1/me/watchlist/intraday?symbol=')) {
      final local = DateTime.now().toUtc().add(const Duration(hours: 8));
      final day = DateTime(local.year, local.month, local.day);
      final prior = day.subtract(const Duration(days: 3));
      return {
        'as_of': day.toIso8601String().substring(0, 10),
        'previous_close': '1000',
        'previous_close_date': prior.toIso8601String().substring(0, 10),
        'previous_close_source': 'official_previous_close',
        'items': [
          for (var i = 0; i < 3; i++)
            {
              'date': day.toIso8601String().substring(0, 10) +
                  'T09:0' + i.toString() + ':00+08:00',
              'value': (1000 + i).toString(),
              'source': 'shioaji_kbars',
            },
        ],
      };
    }
    if (path.startsWith('/api/v1/public/kline/')) return {'rows': [
      for (var i = 0; i < 120; i++)
        {
          'trade_date': DateTime(2026, 6, 1).add(Duration(days: i))
              .toIso8601String().substring(0, 10),
          'close': (1000 + i).toString(),
        },
    ]};
    return {};
  }
}

void main() {
  void phone(WidgetTester tester) {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  testWidgets('Default Watchlist loads only one watch-symbol minute chart',
      (tester) async {
    phone(tester);
    final api = WatchTwoTabsApi();
    await tester.pumpWidget(MaterialApp(home: FinalWatchlistPage(api)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('watch-tab-live')), findsOneWidget);
    expect(find.byKey(const Key('watch-tab-longterm')), findsOneWidget);
    expect(find.byKey(const Key('watch-symbol-strip')), findsOneWidget);
    expect(find.byKey(const Key('watch-minute-chart-2330')), findsOneWidget);
    expect(find.text('已持有'), findsOneWidget);
    expect(api.calls, contains('/api/v1/me/watchlist/intraday?symbol=2330'));
    expect(api.calls.where((p) => p.contains('/public/kline')), isEmpty);
    expect(find.byKey(const ValueKey('watch-2330')), findsNothing);

    await tester.tap(find.byKey(const Key('watch-tab-longterm')));
    await tester.pumpAndSettle();
    expect(api.calls, contains('/api/v1/public/kline/2330?limit=120'));
    expect(find.byKey(const Key('watch-minute-chart-2330')), findsNothing);
    await tester.ensureVisible(find.byKey(const Key('watch-history-60')));
    await tester.tap(find.byKey(const Key('watch-history-60')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('watch-history-chart-2330-60')), findsOneWidget);

    // The chart is long and the picker may sit above the viewport.
    // Move the *outer* list, then the picker scrolls horizontally if needed.
    await tester.drag(find.byKey(const Key('final-watchlist-scroll')),
        const Offset(0, 570));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('watch-select-2327')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('watch-select-2327')));
    await tester.pumpAndSettle();
    expect(api.calls, contains('/api/v1/public/kline/2327?limit=120'));
    expect(find.text('已退出有效名冊 · 仍保留關注'), findsOneWidget);
    await tester.tap(find.byKey(const Key('watch-tab-live')));
    await tester.pumpAndSettle();
    expect(api.calls, contains('/api/v1/me/watchlist/intraday?symbol=2327'));
    expect(find.byKey(const Key('watch-minute-chart-2327')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Watchlist management starts folded and can show original cards',
      (tester) async {
    phone(tester);
    await tester.pumpWidget(MaterialApp(
        home: FinalWatchlistPage(WatchTwoTabsApi())));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('watch-2330')), findsNothing);
    final toggle = find.byKey(const Key('watch-manage-toggle'));
    // Expanding this control requires a vertical scroll of the outer page,
    // not a horizontal scroll of the ticker-strip list.
    await tester.drag(find.byKey(const Key('final-watchlist-scroll')),
        const Offset(0, -640));
    await tester.pumpAndSettle();
    await tester.ensureVisible(toggle);
    await tester.pumpAndSettle();
    await tester.tap(toggle);
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('watch-2330')), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Inactive watchlist does not fetch owner or public history',
      (tester) async {
    final api = WatchTwoTabsApi();
    await tester.pumpWidget(MaterialApp(
        home: FinalWatchlistPage(api, active: false)));
    await tester.pumpAndSettle();
    expect(api.calls, isEmpty);
  });
}
