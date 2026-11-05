import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/main.dart' as legacy;

class HomeFinanceApiStub extends legacy.Api {
  HomeFinanceApiStub() : super('test');
  final requests = <String>[];

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

void main() {
  testWidgets('ordinary holdings are first in full two-column grid and ETFs collapsed',
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
    expect(find.text('一般股票 · 3 檔'), findsOneWidget);

    await tester.scrollUntilVisible(find.byKey(const Key('today-etf-toggle')), 160,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.byKey(const Key('today-etf-toggle')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('today-live-holding-0050')), findsOneWidget);
    expect(find.byKey(const Key('today-live-holding-00697B')), findsOneWidget);
    expect(api.requests.where((p) => p == '/api/v1/me/portfolio/intraday?symbol=2330').length, 1);
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

    await tester.scrollUntilVisible(find.text('融資餘額 · 近兩週'), 220,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('融資餘額 · 近兩週'), findsOneWidget);
    expect(find.textContaining('5890.00 億元'), findsWidgets);
    expect(find.textContaining('較前一交易日'), findsWidgets);
    await tester.scrollUntilVisible(find.text('法人資金流向 · 買賣超金額'), 220,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('法人資金流向 · 買賣超金額'), findsOneWidget);
    expect(find.textContaining('比較日 2026-11-03'), findsOneWidget);
    expect(find.text('三大法人當日買賣超 · 股數（長條為相對幅度）'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
