import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/main.dart' as legacy;

class HoldingsP0Api extends legacy.Api {
  HoldingsP0Api(this.snapshot) : super('test');
  final Map<String, dynamic> snapshot;
  final reads = <String>[];
  final posts = <String>[];
  String queueStatus = 'IDLE';

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    posts.add(path);
    if (path == '/api/v1/me/journal/recalculate') {
      queueStatus = 'SUCCEEDED';
      return {'status': 'SUCCEEDED', 'already_active': false};
    }
    return body;
  }


  @override
  Future<dynamic> get(String path) async {
    reads.add(path);
    if (path == '/api/v1/me/portfolio/snapshot' ||
        path == '/api/v1/me/portfolio/quotes') return snapshot;
    if (path == '/api/v1/me/journal/recalculation-status') {
      return {'status': queueStatus, 'can_retry': true};
    }
    return const <dynamic>[];
  }
}

Map<String,dynamic> _snapshot({bool missing = false}) => {
  'ledger_version': 5,
  'session': 'closed',
  'positions': [
    {
      'symbol': '00719B', 'currency': 'TWD', 'shares': '30000',
      'average_cost': '31.16', 'price_status': missing ? 'missing' : 'available',
      'market_price': missing ? null : '31.12',
      'unrealized_pnl': missing ? null : '-1200',
      'unrealized_return': missing ? null : '-0.001283697',
      'change': missing ? null : '0.10',
      'change_percent': missing ? null : '0.00322',
      'day_change_amount': missing ? null : '3000',
      'previous_close': missing ? null : '31.02',
      'previous_close_date': missing ? null : '2026-10-08',
      'price_date': missing ? null : '2026-10-12',
      'price_source': missing ? null : 'tpex_openapi_eod',
      'missing_reason': missing ? 'latest_price_missing' : null,
    }
  ],
  'items': [
    {
      'currency': 'TWD', 'ledger_version': 5,
      'market_value': missing ? null : '933600',
      'unrealized_pnl': missing ? null : '-1200',
      'unrealized_return': missing ? null : '-0.001283697',
      'aggregate_status': missing ? 'withheld' : 'available',
      'valuation_status': missing ? 'partial' : 'available',
      'valuation_date': '2026-10-12',
      'affected_symbols': missing ? ['00719B'] : [],
    }
  ]
};

void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(390,844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('Phone Ledger has one Hero, cumulative upper and daily lower',
      (tester) async {
    _phone(tester);
    final api = HoldingsP0Api(_snapshot());
    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(api,
      now: () => DateTime.utc(2026,10,12,7))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('ledger-market-value-hero')), findsOneWidget);
    expect(find.text('持股市值'), findsOneWidget);
    final pnl = find.byKey(const Key('holding-pnl-00719B'));
    final daily = find.byKey(const Key('holding-day-amount-00719B'));
    await tester.scrollUntilVisible(daily, 180, scrollable: find.byType(Scrollable).first);
    expect(pnl, findsOneWidget);
    expect(find.text('總損益'), findsOneWidget);
    expect(find.text('當日損益'), findsOneWidget);
    expect(tester.getTopLeft(pnl).dx, greaterThan(tester.getTopLeft(daily).dx));
    expect(find.text('00719B · 30,000 股'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Cash and total assets use one decimal ten-thousand TWD without double PnL',
      (tester) async {
    _phone(tester);
    final snapshot = _snapshot();
    snapshot['cash'] = {
      'cash_status': 'available',
      'cash_balance': '345678.90',
      'currency': 'TWD',
    };
    snapshot['total_asset_value'] = '1279278.90';
    snapshot['asset_status'] = 'available';
    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(
      HoldingsP0Api(snapshot), active: false,
      now: () => DateTime.utc(2026, 10, 12, 7))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('ledger-total-assets')), findsOneWidget);
    expect(find.text('現金部位'), findsOneWidget);
    expect(find.text('現金＋持股市值'), findsOneWidget);
    expect(find.text('34.6 萬元'), findsOneWidget);
    expect(find.text('127.9 萬元'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Delayed TWSE quotes still render seven indicative holdings and assets',
      (tester) async {
    _phone(tester);
    final snapshot = _snapshot();
    final original = Map<String, dynamic>.from(snapshot['positions'].first as Map);
    final other = <Map<String, dynamic>>[
      for (final symbol in ['1513', '2327', '2382', '3231', '5876'])
        {
          ...original,
          'symbol': symbol,
          'stock_name': '持股$symbol',
          'price_status': 'stale',
          'reference_eligible': true,
          'price_source': 'twse_mis',
          'price_date': '2026-10-16',
          'market_price': '100',
          'average_cost': '95',
          'unrealized_pnl': '500',
          'unrealized_return': '0.05263',
          'change': '1.5',
          'change_percent': '0.015',
          'day_change_amount': '150',
        },
    ];
    (snapshot['positions'] as List).addAll(other);
    (snapshot['items'] as List)[0] = {
      'currency': 'TWD',
      'ledger_version': 357,
      'aggregate_status': 'withheld',
      'valuation_status': 'stale',
      'affected_symbols': const ['1513', '2327', '2382', '3231', '5876'],
      'priced_market_value': '933600',
      'priced_symbol_count': 1,
      'reference_status': 'available',
      'reference_price_dates': const ['2026-10-15', '2026-10-16'],
      'reference_priced_symbol_count': 6,
      'reference_market_value': '1433600',
      'reference_unrealized_pnl': '1300',
      'reference_unrealized_return': '0.0009',
    };
    snapshot['cash'] = {'cash_status': 'available', 'cash_balance': '1811000'};
    snapshot['asset_status'] = 'incomplete_prices';
    snapshot['reference_asset_status'] = 'available';
    snapshot['reference_total_asset_value'] = '3244600';
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: FinalLedgerPage(
      HoldingsP0Api(snapshot), active: false,
      now: () => DateTime.utc(2026, 10, 16, 5, 12)))));
    await tester.pumpAndSettle();
    expect(find.text('持股參考市值'), findsOneWidget);
    expect(find.text('現金＋參考市值'), findsOneWidget);
    expect(find.text('324.5 萬元'), findsOneWidget);
    expect(find.text('TWD 1,433,600'), findsOneWidget);
    expect(find.textContaining('非正式收盤總額'), findsOneWidget);
    expect(find.text('總額暫不發布'), findsNothing);
    await tester.scrollUntilVisible(find.byKey(const Key('holding-pnl-5876')),
        170, scrollable: find.byType(Scrollable).first);
    expect(find.text('500'), findsWidgets);
    expect(find.textContaining('參考'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('No priced portfolio total displays missing rather than fabricating assets',
      (tester) async {
    _phone(tester);
    final snapshot = _snapshot(missing: true);
    snapshot['cash'] = {'cash_status': 'available', 'cash_balance': '100000'};
    snapshot['total_asset_value'] = null;
    snapshot['asset_status'] = 'incomplete_prices';
    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(
      HoldingsP0Api(snapshot), active: false,
      now: () => DateTime.utc(2026, 10, 12, 7))));
    await tester.pumpAndSettle();
    expect(find.text('10.0 萬元'), findsOneWidget);
    expect(find.text('待完整估值'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Desktop Ledger uses bounded content rail with one readable Hero',
      (tester) async {
    tester.view.physicalSize = const Size(1280, 850);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(
      HoldingsP0Api(_snapshot()), active: false,
      now: () => DateTime.utc(2026, 10, 12, 7))));
    await tester.pumpAndSettle();
    expect(tester.getSize(find.byKey(const Key('final-ledger-scroll'))).width,
      lessThanOrEqualTo(940));
    expect(find.byKey(const Key('ledger-market-value-hero')), findsOneWidget);
    expect(find.text('持股市值'), findsOneWidget);
    expect(find.text('本年已實現損益'), findsOneWidget);
    expect(find.text('ledger v5'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('P0 Owner can manually recalculate when YTD and holdings are already available',
      (tester) async {
    _phone(tester);
    final api = HoldingsP0Api(_snapshot());
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: FinalLedgerPage(api,
      active: false, now: () => DateTime.utc(2026,10,12,7)))));
    await tester.pumpAndSettle();
    // Current-year history is empty => YTD displays zero (not "pending").
    // The manual recovery entry must still exist and be actionable.
    final recalc = find.byKey(const Key('recalculate-pnl'));
    expect(recalc, findsOneWidget);
    await tester.ensureVisible(recalc);
    await tester.pump();
    await tester.tap(recalc);
    await tester.pump();
    expect(api.posts, contains('/api/v1/me/journal/recalculate'));
    expect(find.text('損益已排入重新計算'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('P0 Owner can retry a failed queue even with available holdings',
      (tester) async {
    _phone(tester);
    final api = HoldingsP0Api(_snapshot())..queueStatus = 'FAILED';
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: FinalLedgerPage(api,
      active: false, now: () => DateTime.utc(2026,10,12,7)))));
    await tester.pumpAndSettle();
    final recalc = find.byKey(const Key('recalculate-pnl'));
    expect(recalc, findsOneWidget);
    await tester.ensureVisible(recalc);
    await tester.pump();
    expect(find.text('重新嘗試'), findsOneWidget);
    await tester.tap(recalc);
    await tester.pump();
    expect(api.posts, contains('/api/v1/me/journal/recalculate'));
    expect(tester.takeException(), isNull);
  });

  testWidgets('Missing ETF quote keeps shares and cost without inventing PnL',
      (tester) async {
    _phone(tester);
    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(
      HoldingsP0Api(_snapshot(missing: true)),
      now: () => DateTime.utc(2026,10,12,7))));
    await tester.pumpAndSettle();
    expect(find.text('總額暫不發布'), findsWidgets);
    await tester.scrollUntilVisible(find.byKey(const Key('holding-pnl-00719B')),
      180, scrollable: find.byType(Scrollable).first);
    expect(find.text('00719B · 30,000 股'), findsOneWidget);
    expect(find.text('成本 31.16'), findsOneWidget);
    expect(find.text('待估值'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
