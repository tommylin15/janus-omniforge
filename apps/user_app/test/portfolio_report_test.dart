import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_portfolio_report.dart';
import 'package:janus_user_app/main.dart' as legacy;

class ReportApi extends legacy.Api {
  ReportApi(this.data) : super('test');
  final Map<String, dynamic> data;
  int historyRequests = 0;

  @override
  Future<dynamic> get(String path) async {
    if (path == '/api/v1/me/portfolio/value-history?days=1825') {
      historyRequests++;
      return data;
    }
    return const <String, dynamic>{};
  }
}

Map<String, dynamic> snapshot({bool missingEtf = false}) => {
  'positions': [
    {'symbol': '2330', 'stock_name': '台積電', 'currency': 'TWD',
      'instrument_kind': 'EQUITY', 'shares': '10', 'price_status': 'available',
      'market_value': '12000'},
    {'symbol': '0050', 'stock_name': '元大台灣50', 'currency': 'TWD',
      'instrument_kind': 'ETF', 'shares': '10',
      'price_status': missingEtf ? 'missing' : 'available',
      'market_value': missingEtf ? null : '8000'},
  ],
  'items': [
    {'currency': 'TWD', 'market_value': missingEtf ? null : '20000',
      'aggregate_status': missingEtf ? 'withheld' : 'available'},
  ],
};

Map<String, dynamic> history({bool single = false}) => {
  'status': single ? 'insufficient_history' : 'available',
  'truncated': false,
  'points': [
    {
      'date': '2026-09-30', 'status': 'available',
      'market_value': '16000', 'cost_basis': '15000',
      'positions': [
        {'symbol': '2330', 'instrument_kind': 'EQUITY',
          'market_value': '10000', 'cost_basis': '9500', 'status': 'available'},
        {'symbol': '0050', 'instrument_kind': 'ETF',
          'market_value': '6000', 'cost_basis': '5500', 'status': 'available'},
      ],
    },
    if (!single)
      {
        'date': '2026-10-30', 'status': 'available',
        'market_value': '20000', 'cost_basis': '18500',
        'positions': [
          {'symbol': '2330', 'instrument_kind': 'EQUITY',
            'market_value': '12000', 'cost_basis': '11000', 'status': 'available'},
          {'symbol': '0050', 'instrument_kind': 'ETF',
            'market_value': '8000', 'cost_basis': '7500', 'status': 'available'},
        ],
      },
  ],
};

void phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

Future<void> open(WidgetTester tester, ReportApi api,
    {bool missingEtf = false}) async {
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: SafeArea(
    child: SingleChildScrollView(
      child: Padding(padding: const EdgeInsets.all(12),
        child: FvPortfolioReport(api: api, snapshot: snapshot(missingEtf: missingEtf))),
    ),
  ))));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('allocation and per-symbol filters on narrow mobile', (tester) async {
    phone(tester);
    final api = ReportApi(history());
    await open(tester, api);
    expect(find.byKey(const Key('portfolio-allocation-pie')), findsOneWidget);
    expect(find.textContaining('20,000'), findsWidgets);
    expect(find.byKey(const Key('portfolio-report-symbol-2330')), findsOneWidget);
    expect(find.byKey(const Key('portfolio-report-symbol-0050')), findsOneWidget);
    await tester.tap(find.byKey(const Key('portfolio-report-etfs')));
    await tester.pumpAndSettle();
    expect(find.textContaining('12,000'), findsWidgets);
  });

  testWidgets('historical view draws only distinct real saved months', (tester) async {
    phone(tester);
    final api = ReportApi(history());
    await open(tester, api);
    await tester.tap(find.text('持股市值走勢'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('portfolio-value-trend-chart')), findsOneWidget);
    expect(find.textContaining('市值變動包含加碼'), findsOneWidget);
    expect(api.historyRequests, 1);
  });

  testWidgets('missing quote does not contribute fake zero', (tester) async {
    phone(tester);
    await open(tester, ReportApi(history()), missingEtf: true);
    expect(find.textContaining('未計價'), findsWidgets);
    expect(find.textContaining('12,000'), findsWidgets);
  });

  testWidgets('single historical valuation shows bounded empty state', (tester) async {
    phone(tester);
    await open(tester, ReportApi(history(single: true)));
    await tester.tap(find.text('持股市值走勢'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('portfolio-value-trend-chart')), findsNothing);
    expect(find.textContaining('至少兩期正式估值'), findsOneWidget);
  });
}
