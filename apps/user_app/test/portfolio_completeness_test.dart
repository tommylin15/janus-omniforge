import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/main.dart';

class PortfolioFakeApi extends Api {
  PortfolioFakeApi(this.values) : super('test');
  final Map<String, dynamic> values;

  @override
  Future<dynamic> get(String path) async => values[path] ?? const [];

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async =>
      values[path] ?? body;

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async =>
      values[path] ?? body;
}

Map<String, dynamic> availableSummary() => {
      'items': [
        {
          'currency': 'TWD',
          'market_value': '240',
          'cost_basis': '200',
          'unrealized_pnl': '40',
          'unrealized_return': '0.2',
          'aggregate_status': 'available',
          'affected_symbol_count': 0,
          'affected_symbols': <String>[],
          'missing_price_count': 0,
          'stale_price_count': 0,
          'valuation_status': 'available',
          'valuation_date': '2026-09-26'
        }
      ]
    };

Map<String, dynamic> withheldSummary() => {
      'items': [
        {
          'currency': 'TWD',
          'market_value': null,
          'cost_basis': '200',
          'unrealized_pnl': null,
          'unrealized_return': null,
          'aggregate_status': 'withheld',
          'affected_symbol_count': 1,
          'affected_symbols': ['2330'],
          'missing_price_count': 1,
          'stale_price_count': 0,
          'valuation_status': 'partial',
          'valuation_date': '2026-09-26',
          'cash_safety_status': 'insufficient_data'
        }
      ]
    };

void main() {
  testWidgets('holdings prefer canonical stock name and show formal return',
      (tester) async {
    final year = DateTime.now().year;
    final api = PortfolioFakeApi({
      '/api/v1/me/portfolio/summary': availableSummary(),
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/notes': const [],
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/journal/positions': [
        {
          'symbol': '2330',
          'stock_name': '台積電',
          'currency': 'TWD',
          'shares': '2',
          'average_cost': '100',
          'market_price': '120',
          'market_value': '240',
          'unrealized_pnl': '40',
          'unrealized_return': '0.2',
          'price_status': 'available',
          'price_date': '2026-09-26',
          'valuation_date': '2026-09-26'
        }
      ]
    });

    await tester.pumpWidget(MaterialApp(home: JournalNotesPage(api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('持股'));
    await tester.pumpAndSettle();

    expect(find.text('台積電（2330） · TWD'), findsOneWidget);
    expect(find.textContaining('未實現報酬 20.00%'), findsOneWidget);
    expect(find.textContaining('估值日 2026-09-26'), findsOneWidget);
    expect(find.textContaining('行情日 2026-09-26'), findsOneWidget);
  });

  testWidgets('holdings expose a safe missing-price reason', (tester) async {
    final year = DateTime.now().year;
    final api = PortfolioFakeApi({
      '/api/v1/me/portfolio/summary': withheldSummary(),
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/notes': const [],
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/journal/positions': [
        {
          'symbol': '2330',
          'stock_name': '台積電',
          'currency': 'TWD',
          'shares': '2',
          'average_cost': '100',
          'market_price': null,
          'market_value': null,
          'unrealized_pnl': null,
          'unrealized_return': null,
          'price_status': 'missing',
          'price_date': null,
          'missing_reason': 'no_eligible_persisted_ohlcv',
          'valuation_date': '2026-09-26'
        }
      ]
    });

    await tester.pumpWidget(MaterialApp(home: JournalNotesPage(api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('持股'));
    await tester.pumpAndSettle();

    expect(find.textContaining('缺少符合估值日的正式行情'), findsOneWidget);
  });

  testWidgets('transaction list prefers canonical stock name plus symbol',
      (tester) async {
    final year = DateTime.now().year;
    final month = DateTime.now().month.toString().padLeft(2, '0');
    final api = PortfolioFakeApi({
      '/api/v1/me/portfolio/summary': availableSummary(),
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/notes': const [],
      '/api/v1/me/journal/history?year=$year': [
        {
          'event_id': 'A',
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'symbol': '2330',
          'stock_name': '台積電',
          'trade_date': '$year-$month-01',
          'shares': '2',
          'price': '100',
          'net_cash_flow': '-200',
          'currency': 'TWD',
          'record_version': 1
        }
      ],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
    });

    await tester.pumpWidget(MaterialApp(home: JournalNotesPage(api)));
    await tester.pumpAndSettle();

    expect(find.text('買進 · 台積電（2330）'), findsOneWidget);
  });

  testWidgets('withheld aggregate never renders a partial total', (tester) async {
    final year = DateTime.now().year;
    final api = PortfolioFakeApi({
      '/api/v1/me/portfolio/summary': withheldSummary(),
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/notes': const [],
    });

    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SummaryCards(api))));
    await tester.pumpAndSettle();

    expect(find.text('總額暫不發布'), findsWidgets);
    expect(find.textContaining('受影響 1 檔：2330'), findsOneWidget);
  });
}
