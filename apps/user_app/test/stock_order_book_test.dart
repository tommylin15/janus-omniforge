import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/stock_order_book.dart';

void main() {
  testWidgets('five authentic levels and quantities, manual refresh and timestamp',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    var calls = 0;
    final future = Future<dynamic>.value({
      'symbol': '2330', 'status': 'available', 'source': 'shioaji_bidask',
      'unit': 'lots', 'quote_at': '2026-11-06T10:02:03+08:00',
      'bid': [for (var i = 0; i < 5; i++)
        {'price': '${100 - i}', 'volume': 10 + i}],
      'ask': [for (var i = 0; i < 5; i++)
        {'price': '${101 + i}', 'volume': 20 + i}],
    });
    await tester.pumpWidget(MaterialApp(home: Scaffold(body:
      StockOrderBookPanel(symbol: '2330', snapshot: future,
        onRefresh: () => calls++))));
    await tester.pumpAndSettle();
    expect(find.text('買賣五檔｜按需快照'), findsOneWidget);
    expect(find.text('委買 60 張'), findsOneWidget);
    expect(find.text('委賣 110 張'), findsOneWidget);
    expect(find.textContaining('2026-11-06 10:02:03'), findsOneWidget);
    expect(find.textContaining('5 · 96'), findsOneWidget);
    await tester.tap(find.byKey(const Key('today-order-book-refresh-2330')));
    expect(calls, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('missing/stale and ticker replacement never present old book',
      (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body:
      StockOrderBookPanel(symbol: '2327', snapshot: Future.value({
        'symbol': '2330', 'status': 'available',
        'bid': [{'price':'100', 'volume':300}],
        'ask': [{'price':'101', 'volume':100}],
      }), onRefresh: () {}))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('today-order-book-missing-2327')), findsOneWidget);
    expect(find.textContaining('委買 300'), findsNothing);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body:
      StockOrderBookPanel(symbol: '2327', snapshot: Future.value({
        'symbol': '2327', 'status': 'stale',
        'bid': [], 'ask': [],
      }), onRefresh: () {}))));
    await tester.pumpAndSettle();
    expect(find.textContaining('已過時'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
