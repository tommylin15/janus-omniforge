import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/main.dart';

class QuotesApi extends Api {
  QuotesApi() : super('test');
  int calls = 0;
  bool fail = false;
  bool stale = false;
  bool marketOpen = true;
  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    if (path == '/api/v1/me/portfolio/quotes/refresh') {
      return get('/api/v1/me/portfolio/quotes');
    }
    return body;
  }

  @override
  Future<dynamic> get(String path) async {
    if (path == '/api/v1/me/portfolio/quotes') {
      calls++;
      if (fail) throw Exception('offline');
      return {
        'positions': [
          {
            'symbol': '2330',
            'stock_name': '台積電',
            'currency': 'TWD',
            'shares': '1234',
            'average_cost': '100.25',
            'market_price': '101.35',
            'market_value': '125065.90',
            'unrealized_pnl': '1357.40',
            'unrealized_return': '0.011',
            'quote_at': DateTime.now().toIso8601String(),
            'valuation_kind': 'intraday',
            'price_status': stale ? 'stale' : 'available'
          }
        ],
        'items': [
          {
            'currency': 'TWD',
            'market_value': '125065.90',
            'unrealized_pnl': '1357.40',
            'unrealized_return': '0.011',
            'aggregate_status': stale ? 'stale' : 'available',
            'stale_price_count': stale ? 1 : 0,
            'valuation_date': '2026-10-01'
          }
        ],
        'checked_at': '2026-10-01T10:00:00+08:00',
        'market_open': marketOpen
      };
    }
    return path.contains('/summary') ? {'items': []} : [];
  }
}

class SlowSummaryApi extends QuotesApi {
  @override
  Future<dynamic> get(String path) async {
    await Future<void>.delayed(const Duration(seconds: 12));
    return super.get(path);
  }
}

void main() {
  testWidgets('after hours fetches once on entry and permits manual refresh',
      (tester) async {
    final api = QuotesApi()..marketOpen = false;
    await tester.pumpWidget(MaterialApp(
        home: JournalNotesPage(api, now: () => DateTime.utc(2026, 10, 1, 6))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('持股'));
    await tester.pumpAndSettle();
    expect(api.calls, 1);
    await tester.pump(const Duration(minutes: 2));
    expect(api.calls, 1);
    await tester.tap(find.text('更新持股股價'));
    await tester.pumpAndSettle();
    expect(api.calls, 2);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('summary accepts a slow successful cold-start response',
      (tester) async {
    await tester.pumpWidget(MaterialApp(home: SummaryCards(SlowSummaryApi())));
    await tester.pump(const Duration(seconds: 9));
    expect(find.text('投資組合摘要暫時無法使用'), findsNothing);
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();
    expect(find.textContaining('待完成筆記'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  test(
      'integer accounting display retains missing values and exact large integers',
      () {
    expect(accountingNumber('1234567.5'), '1,234,568');
    expect(accountingNumber('-1234.5'), '(1,235)');
    expect(accountingNumber('-0.4'), '0');
    expect(accountingNumber('9007199254740993.1'), '9,007,199,254,740,993');
    expect(accountingNumber(null), '—');
    expect(accountingNumber('NaN'), '—');
    expect(accountingNumber('0E-10'), '0');
    expect(accountingNumber('-1.235E3', decimals: 2), '(1,235.00)');
    expect(accountingNumber('9.0071992547409931E15'), '9,007,199,254,740,993');
    expect(accountingNumber('1E-3', decimals: 2), '0.00');
    expect(accountingNumber('1E1000'), '—');
    expect(accountingNumber('1234.565', decimals: 2), '1,234.57');
    expect(accountingNumber('48', decimals: 2), '48.00');
    expect(accountingNumber('-0.004', decimals: 2), '0.00');
    expect(accountingNumber('-1234.565', decimals: 2), '(1,234.57)');
    expect(portfolioReturnLabel('0.1234'), '12%');
  });
  testWidgets(
      'poll only visible foreground holdings, manual refresh, preserve on error',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final api = QuotesApi();
    await tester.pumpWidget(MaterialApp(
        home: JournalNotesPage(api, now: () => DateTime.utc(2026, 10, 1, 2))));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 60));
    expect(api.calls, 0);
    await tester.tap(find.text('持股'));
    await tester.pumpAndSettle();
    expect(api.calls, 1);
    expect(find.textContaining('持有 1,234 股'), findsOneWidget);
    expect(find.textContaining('市值 125,066'), findsOneWidget);
    expect(find.textContaining('現價 101.35 · 均價 100.25'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pump(const Duration(seconds: 59));
    await tester.pumpAndSettle();
    expect(api.calls, 1);
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();
    expect(api.calls, 2);
    await tester.tap(find.text('更新持股股價'));
    await tester.pumpAndSettle();
    expect(api.calls, 3);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump(const Duration(seconds: 60));
    expect(api.calls, 3);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(api.calls, 4);
    api.stale = true;
    await tester.pump(const Duration(minutes: 1));
    await tester.pumpAndSettle();
    expect(find.textContaining('保留最後成功報價估值'), findsOneWidget);
    expect(find.textContaining('市值 125,066'), findsOneWidget);
    api.fail = true;
    await tester.pump(const Duration(minutes: 1));
    await tester.pumpAndSettle();
    expect(find.textContaining('保留最後資料'), findsOneWidget);
    expect(find.textContaining('持有 1,234 股'), findsOneWidget);
    await tester.tap(find.text('紀錄'));
    await tester.pumpAndSettle();
    final calls = api.calls;
    await tester.pump(const Duration(seconds: 60));
    expect(api.calls, calls);
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 60));
    expect(api.calls, calls);
  });
}
