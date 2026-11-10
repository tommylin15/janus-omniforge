import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/final_visual_series.dart';
import 'package:janus_user_app/main.dart' as legacy;

class TodayApiStub extends legacy.Api {
  TodayApiStub(this.market) : super('test');
  final Map<String, dynamic> market;
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
    if (path == '/api/v1/public/market-home') return market;
    return const <String, dynamic>{};
  }
}

class TodayHoldingsApiStub extends TodayApiStub {
  TodayHoldingsApiStub(super.market);

  @override
  Future<dynamic> get(String path) async {
    if (path == '/api/v1/me/portfolio/quotes') {
      requests.add(path);
      return {
        'market_open': false,
        'positions': [
          {'symbol': '2330', 'stock_name': '台積電', 'currency': 'TWD',
           'price_date': '2026-11-03', 'market_price': '1000',
           'quote_state': 'stale', 'price_status': 'stale',
           'price_source': 'shioaji'},
          {'symbol': '2327', 'stock_name': '國巨', 'currency': 'TWD',
           'price_date': '2026-11-03', 'market_price': '550',
           'quote_state': 'stale', 'price_status': 'stale',
           'price_source': 'shioaji'},
        ],
      };
    }
    if (path == '/api/v1/me/portfolio/intraday?symbol=2330') {
      requests.add(path);
      return {
        'symbol': '2330', 'as_of': '2026-11-04',
        'previous_close': '1000', 'previous_close_date': '2026-11-03',
        'previous_close_source': 'official_previous_close',
        'observation_kind': 'page_demanded_minutes',
        'items': [
          {'date': '2026-11-04T09:01:00+08:00', 'value': '1010'},
          {'date': '2026-11-04T09:02:00+08:00', 'value': '990'},
        ],
      };
    }
    return super.get(path);
  }
}

class DeferredTodayApiStub extends TodayApiStub {
  DeferredTodayApiStub(super.market);
  final marketResponse = Completer<dynamic>();
  @override
  Future<dynamic> get(String path) {
    if (path == '/api/v1/public/market-home') {
      requests.add(path);
      return marketResponse.future;
    }
    return super.get(path);
  }
}

void _mobile(WidgetTester tester) {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  test('intraday axis follows actual extremes, keeps zero and has a quiet-market floor', () {
    final falling = fvIntradayAxisRange([-7.17, -9.89, -6.55]);
    expect(falling.min, lessThan(-9.89));
    expect(falling.max, greaterThan(0));
    expect(falling.max, lessThan(2));
    final quiet = fvIntradayAxisRange([0.01, 0.03]);
    expect(quiet.max - quiet.min, greaterThanOrEqualTo(0.6));
    final rising = fvIntradayAxisRange([1.8, 2.7]);
    expect(rising.max, greaterThan(2.7));
    expect(rising.min, lessThan(0));
  });

  testWidgets('TAIEX published 30-day trend changes period and zooms without API refetch',
      (tester) async {
    _mobile(tester);
    final observations = List.generate(30, (day) => {
      'date': DateTime(2026, 9, 1 + day).toIso8601String().substring(0, 10),
      'value': (46000 + day * 100).toString(),
      'source_id': 'taiex', 'provenance_id': 'source' + day.toString(),
    });
    final api = TodayApiStub({
      'schema_version': 'market-home.v1', 'status': 'partial',
      'sections': {
        'taiex': {'status': 'available', 'as_of': '2026-10-08',
          'data': {'close': '49313.44', 'history_points': observations,
            'history_as_of': '2026-09-30',
            'history_source_ids': ['taiex'], 'history_status': 'available'}},
        'market-activity': {'status': 'partial', 'as_of': '2026-10-08',
          'data': {'day_trade_shares': '100000',
            'day_trade_buy_twd': '900000', 'day_trade_sell_twd': '600000'}},
        'institutional': {'status': 'partial', 'as_of': '2026-10-08',
          'data': {'foreign_net_shares': '-500000',
            'investment_trust_net_shares': '200000',
            'dealer_net_shares': '0'}},
      },
    });
    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('today-tab-longterm')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byKey(const Key('today-trend-5')), 180,
      scrollable: find.byType(Scrollable).first);
    expect(find.text('加權指數走勢'), findsOneWidget);
    expect(find.textContaining('正式收盤截至 2026-09-30'), findsOneWidget);
    final before = api.requests.length;
    await tester.tap(find.byKey(const Key('today-trend-5')));
    await tester.pumpAndSettle();
    expect(api.requests.length, before);
    await tester.tap(find.byKey(const Key('today-trend-30')));
    await tester.pumpAndSettle();
    expect(api.requests.length, before);
    // The period chips and zoom icon are at different vertical offsets.
    // Scroll the zoom control back into the visible 390x844 viewport.
    await tester.ensureVisible(find.byKey(const Key('today-taiex-expand')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('today-taiex-expand')));
    await tester.pumpAndSettle();
    expect(find.text('加權指數 · 官方收盤走勢'), findsOneWidget);
    expect(api.requests.length, before);
    await tester.tap(find.byTooltip('關閉大盤走勢'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });


  testWidgets('minute volume renders only real Shioaji Kbar entries', (tester) async {
    _mobile(tester);
    final today = DateTime.now().toUtc().add(const Duration(hours: 8));
    final day = '${today.year}-${today.month.toString().padLeft(2, '0')}-'
        '${today.day.toString().padLeft(2, '0')}';
    Widget display(List<dynamic> rows) => MaterialApp(home: Scaffold(
      body: SingleChildScrollView(child: FvIntradayProgressChart(
        rows: rows, label: '2330 分鐘量', unit: '元／股',
        previousClose: 100, height: 150,
      )),
    ));
    await tester.pumpWidget(display([
      {'date': '${day}T09:00:00+08:00', 'value': '101',
       'volume': '82', 'source': 'shioaji_kbars'},
      {'date': '${day}T09:01:00+08:00', 'value': '102',
       'volume': '43', 'source': 'shioaji_kbars'},
    ]));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('intraday-session-volume-chart')), findsOneWidget);
    expect(find.byKey(const Key('intraday-volume-missing')), findsNothing);
    await tester.pumpWidget(display([
      {'date': '${day}T09:00:00+08:00', 'value': '101',
       'volume': '82', 'source': 'shioaji'},
    ]));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('intraday-session-volume-chart')), findsNothing);
    expect(find.byKey(const Key('intraday-volume-missing')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Today hides stale highlights and marks actual observed intraday extrema',
      (tester) async {
    _mobile(tester);
    final local = DateTime.now().toUtc().add(const Duration(hours: 8));
    final day = '${local.year.toString().padLeft(4, '0')}-'
        '${local.month.toString().padLeft(2, '0')}-'
        '${local.day.toString().padLeft(2, '0')}';
    // The baseline must use a recent prior session on any test date.
    var previousTradingDay = DateTime(local.year, local.month, local.day)
        .subtract(const Duration(days: 1));
    while (previousTradingDay.weekday > DateTime.friday) {
      previousTradingDay =
          previousTradingDay.subtract(const Duration(days: 1));
    }
    final previousDate = previousTradingDay.toIso8601String().substring(0, 10);
    final api = TodayApiStub({
      'sections': {
        'taiex': {'status': 'available', 'as_of': day,
          'data': {'close': '43000', 'intraday_points': [
            {'date': '${day}T09:00:00+08:00', 'value': '42800'},
            {'date': '${day}T09:01:00+08:00', 'value': '43000'},
            {'date': '${day}T09:02:00+08:00', 'value': '42500'},
          ], 'history_points': [
            {'date': previousDate, 'value': '42500'},
          ]}},
      },
    });
    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pumpAndSettle();
    expect(find.text('今天值得看'), findsNothing);
    expect(api.requests.where((p) => p.contains('today-changes')), isEmpty);
    expect(find.byKey(const Key('today-tab-live')), findsOneWidget);
    await tester.tap(find.byKey(const Key('today-market-summary')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('intraday-observed-high')));
    expect(find.textContaining('09:01'), findsWidgets);
    expect(find.textContaining('09:02'), findsWidgets);
    expect(find.byKey(const Key('session-start-0900')), findsOneWidget);
    expect(find.byKey(const Key('session-end-1330')), findsOneWidget);
    expect(find.byKey(const Key('intraday-observed-low')), findsOneWidget);
    expect(find.byKey(const Key('intraday-observed-high-percent')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Owner holdings summary uses dated quotes and bounded minute series',
      (tester) async {
    _mobile(tester);
    final api = TodayHoldingsApiStub({
      'sections': {
        'taiex': {'status': 'available', 'data': {'close': '43000',
          'intraday_points': [
            {'date': '2026-11-04T09:01:00+08:00', 'value': '43000'},
            {'date': '2026-11-04T09:02:00+08:00', 'value': '42900'},
          ]}},
      },
    });
    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('持股今日走勢'), 180,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('持股今日走勢'), findsOneWidget);
    expect(find.byKey(const Key('today-holding-picker')), findsOneWidget);
    expect(find.textContaining('非即時 · 價格日 2026-11-03'), findsWidgets);
    expect(api.requests.where((p) => p == '/api/v1/me/portfolio/intraday?symbol=2330').length, 1);
    await tester.scrollUntilVisible(find.textContaining('2330 · 今日分鐘走勢'), 140,
        scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('09:01'), findsWidgets);
    expect(find.textContaining('09:02'), findsWidgets);
    expect(find.text('今天值得看'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Cold homepage response after nine seconds still paints chart automatically',
      (tester) async {
    _mobile(tester);
    final api = DeferredTodayApiStub({
      'sections': {
        'taiex': {'status': 'available', 'as_of': '2026-10-08',
          'data': {
            'close': '49313', 'history_status': 'available',
            'history_as_of': '2026-10-08',
            'history_source_ids': ['taiex'],
            'history_points': [
              {'date': '2026-10-07', 'value': '49000'},
              {'date': '2026-10-08', 'value': '49313'},
            ]}},
        'institutional': {'status': 'missing', 'data': {}},
        'market-activity': {'status': 'missing', 'data': {}},
      }
    });
    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pump(const Duration(seconds: 10));
    expect(find.text('大盤資料仍在讀取；其他資訊可先使用'), findsOneWidget);
    api.marketResponse.complete(api.market);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('today-market-summary')), findsOneWidget);
    expect(find.text('加權指數'), findsOneWidget);
    expect(api.requests.where((p) => p == '/api/v1/public/market-home').length, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('TAIEX history absent: no fake chart; institutional gaps remain gaps',
      (tester) async {
    _mobile(tester);
    final api = TodayApiStub({
      'sections': {
        'taiex': {'status': 'available',
          'data': {'close': '49313', 'history_points': [
            {'date': '2026-10-08', 'value': '49313'}
          ]}},
        'market-activity': {'status': 'missing', 'data': {}},
        'institutional': {'status': 'missing', 'data': {}},
      }
    });
    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('today-market-summary')));
    await tester.pumpAndSettle();
    expect(find.textContaining('前一正式收盤價缺值'), findsOneWidget);
    expect(find.byKey(const Key('today-taiex-expand')), findsOneWidget);
    await tester.tapAt(const Offset(8, 8)); // dismiss the bottom sheet barrier
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('intraday-session-fixed-chart')), findsNothing);
    await tester.tap(find.byKey(const Key('today-tab-longterm')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.textContaining('法人官方買賣超金額未取得'), 200,
        scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('法人官方買賣超金額未取得'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
