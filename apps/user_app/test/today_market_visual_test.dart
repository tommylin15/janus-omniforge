import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/main.dart' as legacy;

class TodayApiStub extends legacy.Api {
  TodayApiStub(this.market) : super('test');
  final Map<String, dynamic> market;
  final requests = <String>[];

  @override
  Future<dynamic> get(String path) async {
    requests.add(path);
    if (path == '/api/v1/public/market-home') return market;
    return const <String, dynamic>{};
  }
}

void _mobile(WidgetTester tester) {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
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
    await tester.scrollUntilVisible(find.byKey(const Key('today-trend-5')), 180,
      scrollable: find.byType(Scrollable).first);
    expect(find.text('大盤歷史走勢'), findsOneWidget);
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
    expect(find.text('加權指數歷史走勢尚未就緒'), findsOneWidget);
    expect(find.byKey(const Key('today-taiex-expand')), findsNothing);
    expect(find.text('外資　資料缺漏'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
