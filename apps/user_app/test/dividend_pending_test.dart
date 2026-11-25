import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/dividend_pending.dart';
import 'package:janus_user_app/final_ledger.dart';
import 'package:janus_user_app/main.dart' as legacy;

class _DividendFakeApi extends legacy.Api {
  _DividendFakeApi(this.values) : super('test');

  final Map<String, dynamic> values;
  final List<Map<String, dynamic>> calls = [];
  String? confirmError;

  @override
  Future<dynamic> get(String path) async => values[path] ?? const <dynamic>[];

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    calls.add({'method': 'POST', 'path': path, 'body': body});
    if (path == '/api/v1/me/dividends/pending/confirm' && confirmError != null) {
      throw Exception(confirmError);
    }
    if (path == '/api/v1/me/dividends/pending/confirm') {
      values['/api/v1/me/dividends/pending'] = {
        'pending_count': 0,
        'ledger_version': 12,
        'items': const <dynamic>[],
      };
      return {
        'confirmed_count': (body['draft_ids'] as List).length,
        'ledger_version': 12,
        'items': const <dynamic>[],
      };
    }
    if (path == '/api/v1/me/dividends/scan') {
      return {'newly_created': 1, 'recalculated': 0, 'already_recorded': 0};
    }
    return body;
  }

  @override
  Future<dynamic> patch(String path, Map<String, dynamic> body) async {
    calls.add({'method': 'PATCH', 'path': path, 'body': body});
    return body;
  }
}

Map<String, dynamic> _pendingPayload() => {
      'pending_count': 2,
      'ledger_version': 10,
      'items': [
        {
          'draft_id': 'draft-cash-1',
          'symbol': '2884',
          'company_name': '玉山金',
          'action_type': 'CASH_DIVIDEND',
          'ex_date': '2026-08-01',
          'payment_date': '2026-08-28',
          'eligible_shares': '2000',
          'rate_per_share': '1.2',
          'gross_cash_amount': '2400',
          'estimated_remit_fee': '10',
          'estimated_nhi_fee': '0',
          'net_cash_amount': '2390',
          'warnings': const <String>[],
          'status': 'PENDING',
        },
        {
          'draft_id': 'draft-stock-1',
          'symbol': '2884',
          'company_name': '玉山金',
          'action_type': 'STOCK_DIVIDEND',
          'ex_date': '2026-08-01',
          'payment_date': '2026-08-28',
          'eligible_shares': '2000',
          'rate_per_share': '0.1',
          'estimated_stock_shares': '200',
          'fractional_shares': '0',
          'confirmed_stock_shares': '200',
          'warnings': const <String>[],
          'status': 'PENDING',
        },
      ],
    };

Map<String, dynamic> _ledgerValues({Map<String, dynamic>? pending}) => {
      '/api/v1/me/portfolio/snapshot': {
        'ledger_version': 10,
        'session': 'closed',
        'positions': const <dynamic>[],
        'items': const <dynamic>[],
      },
      '/api/v1/me/portfolio/quotes': {
        'session': 'closed',
        'positions': const <dynamic>[],
        'items': const <dynamic>[],
      },
      '/api/v1/me/journal/pnl?year=${DateTime.now().year}': const <dynamic>[],
      '/api/v1/me/journal/recalculation-status': {'status': 'IDLE'},
      '/api/v1/me/journal/records?year=${DateTime.now().year}': {
        'ledger_version': 10,
        'source': 'owner_ledger_derived',
        'history': const <dynamic>[],
        'monthly': const <dynamic>[],
        'symbols': const <dynamic>[],
        'annual': const <dynamic>[],
      },
      '/api/v1/public/market-home': {
        'sections': {'taiex': {'status': 'missing', 'data': {}}},
      },
      if (pending != null) '/api/v1/me/dividends/pending': pending,
    };

void main() {
  testWidgets('FinalLedgerPage displays pending dividends banner and supports batch confirm',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = _DividendFakeApi(_ledgerValues(pending: _pendingPayload()));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FinalLedgerPage(
            api,
            now: () => DateTime.utc(2026, 9, 1),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('pending-dividends-banner')), findsOneWidget);
    expect(find.textContaining('待確認股利（2 筆）'), findsOneWidget);

    await tester.tap(find.byKey(const Key('open-pending-dividends')));
    await tester.pumpAndSettle();

    expect(find.text('待確認股利核對'), findsOneWidget);
    expect(find.text('2884 玉山金'), findsOneWidget);
    expect(find.text('已發放（可核對入帳）'), findsOneWidget);

    // 打開逐筆微調並改為同銀行免匯費 0 元
    await tester.tap(find.byKey(const Key('dividend-edit-draft-cash-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('remit-fee-zero')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('save-dividend-patch')));
    await tester.pumpAndSettle();

    expect(
      api.calls.any((c) =>
          c['method'] == 'PATCH' &&
          c['path'] == '/api/v1/me/dividends/pending/draft-cash-1' &&
          c['body']['estimated_remit_fee'] == '0'),
      isTrue,
    );

    // 一鍵批次確認入帳
    await tester.tap(find.byKey(const Key('confirm-selected-dividends')));
    await tester.pumpAndSettle();

    expect(
      api.calls.any((c) =>
          c['method'] == 'POST' &&
          c['path'] == '/api/v1/me/dividends/pending/confirm' &&
          c['body']['expected_ledger_version'] == 10 &&
          (c['body']['draft_ids'] as List).length == 2),
      isTrue,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('PendingDividendsSheet stays overflow-free at 390px and 200% text scale',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = _DividendFakeApi(_ledgerValues(pending: _pendingPayload()));
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(2.0)),
        child: MaterialApp(
          home: Scaffold(
            body: PendingDividendsSheet(
              api: api,
              now: () => DateTime.utc(2026, 9, 1),
              initialData: _pendingPayload(),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('待確認股利核對'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Records tab provides historical dividend scan action and handles 409 conflict',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = _DividendFakeApi(_ledgerValues(pending: _pendingPayload()))
      ..confirmError = '409 交易版本已變更';

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FinalLedgerPage(
            api,
            now: () => DateTime.utc(2026, 9, 1),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('紀錄'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('scan-historical-dividends')));
    await tester.pumpAndSettle();

    expect(
      api.calls.any((c) => c['path'] == '/api/v1/me/dividends/scan'),
      isTrue,
    );

    // 觸發 409 樂觀鎖衝突，應提示錯誤而不崩潰
    await tester.tap(find.byKey(const Key('confirm-selected-dividends')));
    await tester.pumpAndSettle();
    expect(find.textContaining('交易版本已變動'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
