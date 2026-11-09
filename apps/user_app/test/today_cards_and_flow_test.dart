import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/main.dart' as legacy;

class HomeFinanceApiStub extends legacy.Api {
  HomeFinanceApiStub() : super('test');
  final requests = <String>[];

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    // Historical backfill is separately tested at API/proxy layers.
    // A widget test never contacts a live broker or persists market data.
    if (path == '/api/v1/me/market/minute-backfill') {
      return {'status': 'unavailable', 'saved': 0};
    }
    return const <String, dynamic>{};
  }

  @override
  Future<dynamic> get(String path) async {
    requests.add(path);
    if (path == '/api/v1/public/market-home') {
      return {'status': 'partial', 'sections': {
        'taiex': {'status': 'missing', 'data': {}},
      }};
    }
    if (path == '/api/v1/me/portfolio/quotes') {
      return {'market_open': false, 'positions': [
        for (final symbol in ['0050', '00697B', '00719B'])
          {'symbol': symbol, 'stock_name': 'ETF $symbol', 'currency': 'TWD',
           'instrument_kind': 'ETF', 'price_date': '2026-11-04',
           'market_price': '99', 'quote_state': 'stale', 'price_status': 'stale'},
        for (final symbol in ['2330', '2327', '2382'])
          {'symbol': symbol, 'stock_name': '一般股票 $symbol', 'currency': 'TWD',
           'instrument_kind': 'EQUITY', 'price_date': '2026-11-04',
           'market_price': '150', 'quote_state': 'stale', 'price_status': 'stale'},
      ]};
    }
    if (path.startsWith('/api/v1/me/portfolio/order-book?symbol=')) {
      final symbol = path.split('=').last;
      return {
        'symbol': symbol,
        'status': 'available',
        'source': 'shioaji_bidask',
        'unit': 'lots',
        'quote_at': '2026-11-06T10:01:00+08:00',
        'bid': [
          for (var i = 0; i < 5; i++)
            {'price': '${100 - i}', 'volume': 10 + i}
        ],
        'ask': [
          for (var i = 0; i < 5; i++)
            {'price': '${101 + i}', 'volume': 20 + i}
        ],
      };
    }
    if (path.startsWith('/api/v1/me/portfolio/intraday?symbol=')) {
      return {'items': <Object>[]};
    }
    if (path == '/api/v1/public/market-leverage-flow') {
      return {
        'scope': 'TWSE_listed_only', 'not_intraday': true,
        'margin': {
          'status': 'partial', 'as_of': '2026-11-04',
          'history': [
            {'date': '2026-11-02', 'balance_thousand_twd': '587000000',
             'change_thousand_twd': '-500000'},
            {'date': '2026-11-03', 'balance_thousand_twd': '588000000',
             'change_thousand_twd': '1000000'},
            {'date': '2026-11-04', 'balance_thousand_twd': '589000000',
             'change_thousand_twd': '1000000'},
          ],
        },
        'institutional': {
          'status': 'available', 'as_of': '2026-11-04',
          'previous_as_of': '2026-11-03',
          'items': [
            {'investor_type': 'foreign', 'net_twd': '-1000000000',
             'previous_net_twd': '-500000000', 'delta_twd': '-500000000'},
            {'investor_type': 'trust', 'net_twd': '200000000',
             'previous_net_twd': '100000000', 'delta_twd': '100000000'},
            {'investor_type': 'dealer', 'net_twd': '300000000',
             'previous_net_twd': '200000000', 'delta_twd': '100000000'},
          ],
        },
      };
    }
    return const <String, dynamic>{};
  }
}

class LimitHomeFinanceApiStub extends HomeFinanceApiStub {
  @override
  Future<dynamic> get(String path) async {
    final response = await super.get(path);
    if (path == '/api/v1/me/portfolio/quotes') {
      final data = Map<String, dynamic>.from(response as Map);
      final positions = List<Map<String, dynamic>>.from(
          (data['positions'] as List).map((row) =>
              Map<String, dynamic>.from(row as Map)));
      positions.firstWhere((row) => row['symbol'] == '2327').addAll({
        'market_price': '411.00', 'previous_close': '374',
        'previous_close_source': 'shioaji_previous_close',
        'instrument_kind': 'EQUITY', 'quote_state': 'intraday',
        'price_status': 'available',
      });
      return {...data, 'market_open': true, 'positions': positions};
    }
    return response;
  }
}

void main() {
  testWidgets('Today selector highlights a selected limit-up quote',
      (tester) async {
    tester.view.physicalSize = const Size(390, 850);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        home: FinalTodayPage(LimitHomeFinanceApiStub())));
    await tester.pumpAndSettle();
    final option = find.byKey(const Key('today-live-holding-2327'));
    await tester.ensureVisible(option);
    await tester.pumpAndSettle();
    await tester.tap(option);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('today-selected-limit-price')), findsOneWidget);
    expect(find.text('411.00'), findsOneWidget);
    expect(find.text('漲停'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('ordinary holdings appear in compact ticker strip; arrow and ETF switches reuse one chart',
      (tester) async {
    tester.view.physicalSize = const Size(390, 850);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = HomeFinanceApiStub();
    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(find.byKey(const Key('today-live-holding-2330')), 180,
        scrollable: find.byType(Scrollable).first);
    expect(find.byKey(const Key('today-live-holding-2330')), findsOneWidget);
    expect(find.byKey(const Key('today-live-holding-2327')), findsOneWidget);
    expect(find.byKey(const Key('today-live-holding-2382')), findsOneWidget);
    expect(find.byKey(const Key('today-live-holding-0050')), findsNothing);
    expect(find.text('持股今日走勢'), findsOneWidget);
    expect(find.text('3 股 · 3 ETF'), findsOneWidget);
    expect(find.byKey(const Key('today-holding-symbol-strip')), findsOneWidget);
    // Price, day PnL, cash and asset totals belong to holdings/ledger, not Today.
    expect(find.textContaining('當日持股變動'), findsNothing);
    expect(find.textContaining('參考總資產'), findsNothing);
    expect(find.textContaining('150.00'), findsNothing);
    expect(find.byKey(const Key('today-selected-holding-name')), findsOneWidget);
    await tester.tap(find.byKey(const Key('today-next-holding')));
    await tester.pumpAndSettle();
    expect(find.textContaining('2327 · 今日分鐘走勢'), findsWidgets);
    expect(api.requests.where((p) => p ==
        '/api/v1/me/portfolio/order-book?symbol=2327').length, 1);
    expect(api.requests.where((p) => p == '/api/v1/me/portfolio/intraday?symbol=2327').length, 1);


    await tester.ensureVisible(find.byKey(const Key('today-etf-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('today-etf-toggle')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('today-live-holding-0050')), findsOneWidget);
    expect(find.byKey(const Key('today-live-holding-00697B')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('today-live-holding-0050')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('today-live-holding-0050')));
    await tester.pumpAndSettle();
    expect(find.textContaining('0050 · 今日分鐘走勢'), findsWidgets);
    expect(api.requests.where((p) => p == '/api/v1/me/portfolio/intraday?symbol=0050').length, 1);
    expect(api.requests.where((p) => p ==
        '/api/v1/me/portfolio/order-book?symbol=0050').length, 1);
    await tester.ensureVisible(find.byKey(const Key('today-etf-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('today-etf-toggle')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('today-live-holding-0050')), findsNothing);
    expect(find.textContaining('2330 · 今日分鐘走勢'), findsWidgets);
    // Returning to the original ticker correctly fetches one fresh chart.
    expect(api.requests.where((p) => p == '/api/v1/me/portfolio/intraday?symbol=2330').length, 2);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Today tabs keep minute chart separate from long-term research', (tester) async {
    tester.view.physicalSize = const Size(390, 850);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = HomeFinanceApiStub();
    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pumpAndSettle();
    expect(find.text('持股今日走勢'), findsOneWidget);
    expect(find.text('融資餘額 · 近兩週'), findsNothing);
    expect(api.requests.where((p) => p == '/api/v1/public/market-leverage-flow'), isEmpty);
    await tester.tap(find.byKey(const Key('today-tab-longterm')));
    await tester.pumpAndSettle();
    expect(find.text('市場長期趨勢'), findsOneWidget);
    expect(find.text('持股今日走勢'), findsNothing);
    expect(api.requests.where((p) => p == '/api/v1/public/market-leverage-flow').length, 1);
    await tester.tap(find.byKey(const Key('today-tab-live')));
    await tester.pumpAndSettle();
    expect(find.text('持股今日走勢'), findsOneWidget);
    await tester.tap(find.byKey(const Key('today-tab-longterm')));
    await tester.pumpAndSettle();
    expect(api.requests.where((p) => p == '/api/v1/public/market-leverage-flow').length, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('credit panel uses dated TWD financing and investor money deltas',
      (tester) async {
    tester.view.physicalSize = const Size(390, 850);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = HomeFinanceApiStub();
    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pumpAndSettle();

    expect(api.requests.where((p) =>
        p == '/api/v1/public/market-leverage-flow'), isEmpty);
    await tester.tap(find.byKey(const Key('today-tab-longterm')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('融資餘額 · 近兩週'), 220,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('融資餘額 · 近兩週'), findsOneWidget);
    expect(find.textContaining('5,890.00 億元'), findsWidgets);
    expect(find.textContaining('較前一交易日'), findsWidgets);
    await tester.scrollUntilVisible(find.text('法人資金流向 · 買賣超金額'), 220,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('法人資金流向 · 買賣超金額'), findsOneWidget);
    expect(find.textContaining('比較日 2026-11-03'), findsOneWidget);
    expect(find.text('三大法人當日買賣超 · 股數（長條為相對幅度）'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
