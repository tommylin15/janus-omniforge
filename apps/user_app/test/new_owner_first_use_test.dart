import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/main.dart' as legacy;

class NewOwnerApi extends legacy.Api {
  NewOwnerApi() : super('test');

  Map<String, dynamic> cash = {
    'cash_status': 'not_configured',
    'cash_balance': null,
    'cash_version': 0,
  };
  Map<String, dynamic>? savedCash;
  Map<String, dynamic> brokerProfile = {
    'version': 0,
    'declared_cash': null,
    'cash_as_of': null,
    'currency': 'TWD',
    'rule_version': 'broker-profile.v1',
  };
  Map<String, dynamic>? savedBrokerProfile;
  Map<String, dynamic>? savedTrade;
  final List<String> reads = [];

  @override
  Future<dynamic> get(String path) async {
    reads.add(path);
    if (path == '/api/v1/me/cash-position') return cash;
    if (path == '/api/v1/me/broker-profile') return brokerProfile;
    if (path == '/api/v1/me/portfolio/snapshot' ||
        path == '/api/v1/me/portfolio/quotes') {
      return <String, dynamic>{
        'items': <dynamic>[],
        'positions': <dynamic>[],
        'cash': cash,
        'asset_status': 'missing',
        'session': 'closed',
      };
    }
    if (path == '/api/v1/me/journal/recalculation-status') {
      return {'status': 'IDLE', 'can_retry': false};
    }
    if (path.startsWith('/api/v1/me/journal/instruments?')) {
      return {
        'items': [
          {
            'symbol': '0050',
            'stock_name': '元大台灣50',
            'instrument_kind': 'ETF',
          },
          {
            'symbol': '2330',
            'stock_name': '台積電',
            'instrument_kind': 'EQUITY',
          },
        ],
      };
    }
    return <dynamic>[];
  }

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    if (path == '/api/v1/me/journal/preview') {
      if ((brokerProfile['version'] as int) == 0) {
        throw Exception('請先在券商設定保存手續費折扣與最低費用');
      }
      return {
        'preview': true,
        'based_on_ledger_version': 0,
        'broker_profile_version': brokerProfile['version'],
        'net_cash_flow': '-180256',
        'transaction_realized_pnl': null,
        'remaining_shares': body['shares'],
        'remaining_average_cost': body['price'],
      };
    }
    if (path == '/api/v1/me/journal/events') {
      savedTrade = Map<String, dynamic>.from(body);
      return {
        'event_id': 'evt-1',
        'transaction_result': {'remaining_shares': body['shares']},
      };
    }
    throw StateError(path);
  }

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    if (path == '/api/v1/me/broker-profile') {
      if (body['expected_version'] != brokerProfile['version']) {
        throw StateError('broker profile version conflict');
      }
      savedBrokerProfile = Map<String, dynamic>.from(body);
      brokerProfile = {
        ...brokerProfile,
        ...body,
        'version': (brokerProfile['version'] as int) + 1,
      };
      return brokerProfile;
    }
    if (path != '/api/v1/me/cash-position') throw StateError(path);
    if (body['expected_version'] != cash['cash_version']) {
      throw StateError('cash version conflict');
    }
    savedCash = Map<String, dynamic>.from(body);
    cash = {
      'cash_status': 'available',
      'cash_balance': body['amount'],
      'cash_version': (cash['cash_version'] as int) + 1,
    };
    return cash;
  }
}

void phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('zero-cash owner can save first cash position and read back', (tester) async {
    phone(tester);
    final api = NewOwnerApi();
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: legacy.CashPositionCard(api))));
    await tester.pumpAndSettle();

    expect(find.textContaining('尚未設定'), findsOneWidget);
    await tester.tap(find.byTooltip('修改現金部位'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).last, '20000');
    await tester.tap(find.text('儲存餘額'));
    await tester.pumpAndSettle();

    expect(api.savedCash?['expected_version'], 0);
    expect(api.savedCash?['amount'], '20000');
    expect(find.textContaining('20,000'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('no positions shows first trade and direct cash settings', (tester) async {
    phone(tester);
    final api = NewOwnerApi();
    await tester.pumpWidget(MaterialApp(
      home: FinalLedgerPage(api, active: false),
    ));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('ledger-cash-edit')), findsOneWidget);
    expect(find.byKey(const Key('ledger-first-trade')), findsOneWidget);
    expect(find.textContaining('尚未建立持股'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('first transaction can choose stock from shared instrument master', (tester) async {
    phone(tester);
    final api = NewOwnerApi();
    Map<String, dynamic>? result;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(builder: (context) => FilledButton(
          onPressed: () async {
            result = await legacy.transactionDialog(context, api: api);
          },
          child: const Text('開始交易'),
        )),
      ),
    ));
    await tester.tap(find.text('開始交易'));
    await tester.pumpAndSettle();

    final stockField = find.widgetWithText(TextFormField, '股票／ETF 代號或名稱');
    await tester.enterText(stockField, '2330');
    await tester.pumpAndSettle();
    expect(api.reads.any((path) => path.contains('/journal/instruments?q=2330')), isTrue);
    await tester.tap(find.text('台積電（2330）').last);
    await tester.pumpAndSettle();

    final shares = find.widgetWithText(TextFormField, '股數');
    await tester.ensureVisible(shares);
    await tester.enterText(shares, '100');
    final price = find.widgetWithText(TextFormField, '成交單價');
    await tester.ensureVisible(price);
    await tester.enterText(price, '500');
    await tester.tap(find.text('儲存'));
    await tester.pumpAndSettle();

    expect(result?['symbol'], '2330');
    expect(result?['event_type'], 'BUY');
    expect(result?['shares'], '100');
    expect(tester.takeException(), isNull);
  });

  testWidgets('new owner without broker profile can set fee rate inline and save first trade', (tester) async {
    phone(tester);
    final api = NewOwnerApi();
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: FinalLedgerPage(api, active: false)),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('ledger-first-trade')));
    await tester.pumpAndSettle();

    final stockField = find.widgetWithText(TextFormField, '股票／ETF 代號或名稱');
    await tester.enterText(stockField, '0050');
    await tester.pumpAndSettle();
    await tester.tap(find.text('元大台灣50（0050）').last);
    await tester.pumpAndSettle();

    final shares = find.widgetWithText(TextFormField, '股數');
    await tester.ensureVisible(shares);
    await tester.enterText(shares, '1000');
    final price = find.widgetWithText(TextFormField, '成交單價');
    await tester.ensureVisible(price);
    await tester.enterText(price, '180');
    await tester.tap(find.text('儲存'));
    await tester.pumpAndSettle();

    expect(find.text('設定券商手續費率'), findsOneWidget);
    await tester.tap(find.text('儲存並繼續試算'));
    await tester.pumpAndSettle();

    expect(api.savedBrokerProfile?['expected_version'], 0);
    expect(api.savedBrokerProfile?['fee_discount_multiplier'], '1');
    expect(api.savedBrokerProfile?['minimum_fee'], '20');
    expect(find.text('交易試算'), findsOneWidget);

    await tester.tap(find.text('確認成交並儲存'));
    await tester.pumpAndSettle();

    expect(api.savedTrade?['symbol'], '0050');
    expect(api.savedTrade?['expected_ledger_version'], 0);
    expect(api.savedTrade?['expected_broker_profile_version'], 1);
    expect(tester.takeException(), isNull);
  });
}
