import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/main.dart';

class ReadApi extends Api {
  ReadApi() : super('test');
  final reads = <String>[];
  final notes = Completer<dynamic>();
  bool failPositions = true;
  @override
  Future<dynamic> get(String path) async {
    reads.add(path);
    if (path.contains('/notes?')) return notes.future;
    if (path.endsWith('/positions') && failPositions)
      throw Exception('offline');
    if (path.contains('stock-health'))
      return {
        'data': {'stock_name': '台積電'}
      };
    if (path.contains('market-home')) return {'sections': {}};
    return [];
  }
}

void main() {
  testWidgets('detail isolates slow sections, retries and lazily loads Kline',
      (tester) async {
    final api = ReadApi();
    await tester.pumpWidget(
        MaterialApp(home: StockDetailPage(api: api, symbol: '2330')));
    await tester.pump();
    await tester.pump();
    expect(find.text('2330 台積電'), findsWidgets);
    expect(api.reads.any((path) => path.contains('/kline/')), isFalse);
    expect(find.text('持股資料尚未取得'), findsOneWidget);
    api.failPositions = false;
    await tester.tap(find.text('重試').first);
    await tester.pump();
    await tester.pump();
    expect(find.text('目前無持股'), findsOneWidget);
    final healthReads =
        api.reads.where((path) => path.contains('stock-health')).length;
    api.notes.complete([]);
    await tester.pumpAndSettle();
    expect(api.reads.where((path) => path.contains('stock-health')).length,
        healthReads);
    await tester.scrollUntilVisible(find.text('進階資料'), 300);
    await tester.ensureVisible(find.text('進階資料'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('進階資料'));
    await tester.pumpAndSettle();
    expect(api.reads.where((path) => path.contains('/kline/')).length, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'visited navigation retains requests and owner switch clears state',
      (tester) async {
    final api = ReadApi();
    Widget workspace(Api value) => MaterialApp(
        home: Workspace(api: value, email: 'test', onTheme: (_) {}));
    await tester.pumpWidget(workspace(api));
    await tester.pumpAndSettle();
    expect(api.reads.contains('/api/v1/me/watchlist'), isFalse);
    await tester.tap(find.text('關注'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('今日'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('關注'));
    await tester.pumpAndSettle();
    expect(api.reads.where((path) => path == '/api/v1/me/watchlist').length, 1);
    final other = ReadApi();
    await tester.pumpWidget(workspace(other));
    await tester.pumpAndSettle();
    expect(other.reads.contains('/api/v1/me/watchlist'), isFalse);
  });
}
