import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/final_visual_common.dart';
import 'package:janus_user_app/main.dart' as legacy;

class FinalFakeApi extends legacy.Api {
  FinalFakeApi(this.values) : super('test');

  final Map<String, dynamic> values;
  final reads = <String>[];
  final posts = <String>[];

  @override
  Future<dynamic> get(String path) async {
    reads.add(path);
    final value = values[path];
    if (value is Exception) throw value;
    return value ?? const [];
  }

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    posts.add(path);
    final value = values[path] ??
        (path == '/api/v1/me/portfolio/quotes/refresh'
            ? values['/api/v1/me/portfolio/quotes']
            : null);
    if (value is Exception) throw value;
    return value ?? body;
  }

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async => body;

  @override
  Future<dynamic> patch(String path, Map<String, dynamic> body) async => body;
}

class DeferredLedgerApi extends FinalFakeApi {
  DeferredLedgerApi(super.values);
  final history = Completer<dynamic>();

  @override
  Future<dynamic> get(String path) {
    if (path.startsWith('/api/v1/me/journal/history')) {
      reads.add(path);
      return history.future;
    }
    return super.get(path);
  }
}

void mobileView(WidgetTester tester) {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('390px Today keeps baseline hierarchy without Daily Brief',
      (tester) async {
    mobileView(tester);
    final api = FinalFakeApi({
      '/api/v1/public/market-home': {
        'status': 'available',
        'sections': {
          'taiex': {
            'status': 'available',
            'as_of': '2026-10-02',
            'freshness_days': 0,
            'coverage': {'received_symbols': 1, 'requested_symbols': 1},
            'data': {'close': '48475.74'}
          },
          'market-activity': {
            'status': 'available',
            'as_of': '2026-10-02',
            'data': {'day_trade_shares': '1960842000'}
          },
          'institutional': {
            'status': 'available',
            'as_of': '2026-10-02',
            'data': {'foreign_net_shares': '225187325'}
          },
        }
      },
      '/api/v1/public/daily-brief': {'items': []},
    });

    await tester.pumpWidget(MaterialApp(home: FinalTodayPage(api)));
    await tester.pumpAndSettle();

    expect(find.text('今日'), findsOneWidget);
    expect(find.text('加權指數'), findsOneWidget);
    expect(find.text('櫃買指數'), findsNothing);
    expect(find.text('市場活動'), findsOneWidget);
    expect(find.text('法人動向'), findsOneWidget);
    expect(find.text('外資買賣超股數 225,187,325'), findsOneWidget);
    expect(find.text('研究內容尚未就緒'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('390px Watchlist is owner-centered and preserves off-universe row',
      (tester) async {
    mobileView(tester);
    final api = FinalFakeApi({
      '/api/v1/me/watchlist': [
        {
          'symbol': '2330',
          'stock_name': '台積電',
          'market_price': '1000',
          'price_date': '2026-10-02',
          'price_status': 'available',
          'held': true,
          'target_price': '1100',
          'pending_note_count': 1,
          'in_market_500': false,
          'version': 4,
        }
      ]
    });

    await tester.pumpWidget(MaterialApp(home: FinalWatchlistPage(api)));
    await tester.pumpAndSettle();

    expect(find.text('關注'), findsOneWidget);
    expect(find.text('搜尋股票代號或中文名稱'), findsOneWidget);
    expect(find.text('我的關注 1/50'), findsOneWidget);
    expect(find.text('台積電（2330）'), findsOneWidget);
    expect(find.text('已持有'), findsOneWidget);
    expect(find.text('已離開本週 500 · 仍保留關注'), findsOneWidget);
    expect(find.byIcon(Icons.drag_handle), findsNothing);

    await tester.tap(find.text('搜尋股票代號或中文名稱'));
    await tester.pumpAndSettle();
    expect(find.text('搜尋關注股票'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '搜尋'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '儲存'), findsNothing);
    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  }, variant: TargetPlatformVariant.only(TargetPlatform.windows));

  testWidgets('390px Ledger puts canonical aggregate first and never invents YTD zero',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {
        'items': [
          {
            'currency': 'TWD',
            'market_value': null,
            'cost_basis': '200',
            'unrealized_pnl': null,
            'unrealized_return': null,
            'aggregate_status': 'withheld',
            'affected_symbols': ['2330'],
            'valuation_status': 'partial',
            'ledger_version': 24,
            'valuation_date': '2026-10-05'
          }
        ]
      },
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/positions': [
        {
          'symbol': '2330',
          'stock_name': '台積電',
          'shares': '2',
          'average_cost': '100',
          'market_price': null,
          'unrealized_pnl': null,
          'unrealized_return': null,
          'valuation_date': '2026-10-05',
          'price_status': 'missing'
        }
      ],
      '/api/v1/me/journal/history?year=$year': [
        {
          'event_id': 'pending-event',
          'ledger_version': 24,
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'trade_date': '2026-10-01',
          'symbol': '2330',
          'shares': '2',
          'price': '100',
          'currency': 'TWD',
        }
      ],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
    });

    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(api, now: () => DateTime.utc(2026, 10, 1, 6))));
    await tester.pumpAndSettle();

    expect(find.text('記帳／筆記'), findsOneWidget);
    expect(find.text('持股市值'), findsOneWidget);
    expect(find.text('本年已實現損益'), findsOneWidget);
    expect(find.text('待更新／尚未確認'), findsOneWidget);
    expect(find.byKey(const Key('recalculate-pnl')), findsOneWidget);
    expect(find.text('重新計算損益'), findsOneWidget);
    expect(find.text('總額暫不發布'), findsWidgets);
    expect(find.text('持股'), findsWidgets);
    expect(find.text('紀錄'), findsOneWidget);
    expect(find.text('報表'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger disables duplicate recalc while owner request is active',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {
        'items': [
          {
            'currency': 'TWD',
            'market_value': null,
            'cost_basis': '100',
            'unrealized_pnl': null,
            'unrealized_return': null,
            'aggregate_status': 'withheld',
            'valuation_status': 'partial',
            'ledger_version': 162,
            'valuation_date': '2026-10-06'
          }
        ]
      },
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': [
        {
          'event_id': 'pending-163',
          'ledger_version': 163,
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'trade_date': '2026-10-07',
          'symbol': '2330',
          'shares': '1',
          'price': '100',
          'currency': 'TWD',
        }
      ],
      '/api/v1/me/journal/recalculation-status': {
        'request_id': 'recalc-1',
        'requested_ledger_version': 163,
        'status': 'QUEUED',
        'trigger_source': 'manual',
        'can_retry': false,
      },
      '/api/v1/me/portfolio/quotes': {
        'positions': const [],
        'items': const [],
        'checked_at': '2026-10-07T07:00:00+08:00',
        'market_open': false,
      },
    });

    await tester.pumpWidget(
      MaterialApp(
        home: FinalLedgerPage(
          api,
          active: false,
          now: () => DateTime.utc(2026, 10, 6, 23),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button =
        tester.widget<OutlinedButton>(find.byKey(const Key('recalculate-pnl')));
    expect(button.onPressed, isNull);
    expect(find.text('重算進行中'), findsOneWidget);
    expect(find.text('已排隊，等待重算'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('Ledger surfaces failed recalc reason and permits retry',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {
        'items': [
          {
            'currency': 'TWD',
            'market_value': null,
            'cost_basis': '100',
            'unrealized_pnl': null,
            'unrealized_return': null,
            'aggregate_status': 'withheld',
            'valuation_status': 'partial',
            'ledger_version': 162,
            'valuation_date': '2026-10-06'
          }
        ]
      },
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': [
        {
          'event_id': 'pending-163',
          'ledger_version': 163,
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'trade_date': '2026-10-07',
          'symbol': '2330',
          'shares': '1',
          'price': '100',
          'currency': 'TWD',
        }
      ],
      '/api/v1/me/journal/recalculation-status': {
        'request_id': 'recalc-1',
        'requested_ledger_version': 163,
        'status': 'FAILED',
        'error_code': 'ICEBERG_ERROR',
        'message': 'Private Mart 寫入失敗，已停止本次工作',
        'can_retry': true,
      },
      '/api/v1/me/journal/recalculate': {
        'request_id': 'recalc-2',
        'requested_ledger_version': 163,
        'status': 'QUEUED',
        'already_active': false,
      },
      '/api/v1/me/portfolio/quotes': {
        'positions': const [],
        'items': const [],
        'checked_at': '2026-10-07T07:00:00+08:00',
        'market_open': false,
      },
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FinalLedgerPage(
            api,
            active: false,
            now: () => DateTime.utc(2026, 10, 6, 23),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('重新嘗試'), findsOneWidget);
    expect(
      find.text('重算失敗：Private Mart 寫入失敗，已停止本次工作'),
      findsOneWidget,
    );

    await tester.tap(find.text('重新嘗試'));
    await tester.pumpAndSettle();
    expect(api.posts, contains('/api/v1/me/journal/recalculate'));
    expect(find.text('損益已排入重新計算'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('Ledger confirms zero only when current-year history is confirmed empty',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {
        'items': [
          {
            'currency': 'TWD',
            'market_value': '0',
            'cost_basis': '0',
            'unrealized_pnl': '0',
            'unrealized_return': '0',
            'aggregate_status': 'available',
            'valuation_status': 'available',
            'ledger_version': 0,
            'valuation_date': '2026-10-05'
          }
        ]
      },
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
    });

    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(api, now: () => DateTime.utc(2026, 10, 1, 6))));
    await tester.pumpAndSettle();

    expect(find.text('本年已實現損益'), findsOneWidget);
    expect(find.text('本年度確認無交易'), findsOneWidget);
    expect(find.text('待更新／尚未確認'), findsNothing);
    expect(find.byKey(const Key('recalculate-pnl')), findsNothing);

    await tester.tap(find.text('報表'));
    await tester.pumpAndSettle();
    expect(find.text('本年度確認無交易；已實現損益 0'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger keeps YTD unavailable distinct from confirmed zero',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {'items': const []},
      '/api/v1/me/journal/pnl?year=$year': Exception('pnl unavailable'),
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
    });

    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(api, now: () => DateTime.utc(2026, 10, 1, 6))));
    await tester.pumpAndSettle();

    expect(find.text('年度損益目前無法確認'), findsOneWidget);
    expect(find.text('本年度確認無交易'), findsNothing);

    await tester.tap(find.text('報表'));
    await tester.pumpAndSettle();
    expect(find.text('本年已實現損益目前無法確認'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger uses minus signs and Taiwan red-green colors for aggregate PnL',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {
        'items': [
          {
            'currency': 'TWD',
            'market_value': '950',
            'cost_basis': '1000',
            'unrealized_pnl': '-50',
            'unrealized_return': '-0.05',
            'aggregate_status': 'available',
            'valuation_status': 'available',
            'ledger_version': 2,
            'valuation_date': '2026-10-06'
          }
        ]
      },
      '/api/v1/me/journal/pnl?year=$year': [
        {
          'currency': 'TWD',
          'realized_pnl': '-20',
          'valuation_date': '2026-10-06',
          'ledger_version': 2,
        }
      ],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
    });

    await tester.pumpWidget(MaterialApp(
      home: FinalLedgerPage(
        api,
        active: false,
        now: () => DateTime.utc(2026, 10, 6, 7),
      ),
    ));
    await tester.pumpAndSettle();

    expect(legacy.accountingNumber('-1234'), '-1,234');
    final unrealized = tester.widget<Text>(find.text('TWD -50'));
    final realized = tester.widget<Text>(find.text('TWD -20'));
    final unrealizedReturn = tester.widget<Text>(find.text('報酬 -5%'));
    expect(unrealized.style?.color, fvLoss);
    expect(realized.style?.color, fvLoss);
    expect(unrealizedReturn.style?.color, fvLoss);
    expect(find.textContaining('(50)'), findsNothing);
    expect(find.textContaining('(20)'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger Records preserves append-only correction workflow',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {
        'items': [
          {
            'currency': 'TWD',
            'market_value': '100',
            'cost_basis': '100',
            'unrealized_pnl': '0',
            'unrealized_return': '0',
            'aggregate_status': 'available',
            'valuation_status': 'available',
            'ledger_version': 1,
            'valuation_date': '2026-10-05'
          }
        ]
      },
      '/api/v1/me/journal/pnl?year=$year': [
        {
          'currency': 'TWD',
          'realized_pnl': '0',
          'valuation_date': '2026-10-05'
        }
      ],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': [
        {
          'event_id': 'event-1',
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'trade_date': '2026-10-05',
          'symbol': '2330',
          'stock_name': '台積電',
          'shares': '1',
          'price': '100',
          'fee': '0',
          'tax': '0',
          'currency': 'TWD',
          'net_cash_flow': '-100'
        }
      ],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
    });

    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: FinalLedgerPage(api, now: () => DateTime.utc(2026, 10, 1, 6)))),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('紀錄'));
    await tester.pumpAndSettle();

    expect(find.byTooltip('建立更正'), findsNothing);
    await tester.tap(find.text('$year 年 10 月'));
    await tester.pumpAndSettle();
    expect(find.byTooltip('建立更正'), findsOneWidget);
    await tester.tap(find.byTooltip('建立更正'));
    await tester.pumpAndSettle();
    expect(find.text('建立更正'), findsOneWidget);

    await tester.tap(find.text('儲存'));
    await tester.pumpAndSettle();

    expect(
      api.posts,
      contains('/api/v1/me/journal/events/event-1/corrections'),
    );
    expect(find.text(legacy.portfolioPendingMessage), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger Records deletes by append-only reversal after confirmation',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {'items': const []},
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': [
        {
          'event_id': 'event-delete-1',
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'trade_date': '2026-10-05',
          'symbol': '2330',
          'stock_name': '台積電',
          'shares': '1',
          'price': '100',
          'fee': '0',
          'tax': '0',
          'currency': 'TWD',
          'net_cash_flow': '-100'
        }
      ],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/journal/symbol-summary?year=$year': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
      '/api/v1/me/portfolio/quotes': {
        'positions': const [],
        'items': const [],
        'checked_at': '2026-10-07T07:00:00+08:00',
        'market_open': false,
      },
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FinalLedgerPage(
            api,
            now: () => DateTime.utc(2026, 10, 6, 23),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('紀錄'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('$year 年 10 月'));
    await tester.pumpAndSettle();

    expect(find.byTooltip('刪除交易'), findsOneWidget);
    await tester.tap(find.byTooltip('刪除交易'));
    await tester.pumpAndSettle();
    expect(find.text('刪除這筆交易？'), findsOneWidget);
    expect(find.textContaining('REVERSAL'), findsOneWidget);

    await tester.tap(find.text('確認刪除'));
    await tester.pumpAndSettle();

    expect(
      api.posts,
      contains('/api/v1/me/journal/events/event-delete-1/reversals'),
    );
    expect(find.text('交易已作廢，持股與損益重新計算中'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger Records switches annual detail between month and stock aggregates',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {'items': const []},
      '/api/v1/me/journal/pnl?year=$year': [
        {
          'currency': 'TWD',
          'realized_pnl': '150',
          'valuation_date': '2026-10-06'
        }
      ],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': [
        {
          'event_id': 'event-1',
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'trade_date': '2026-10-05',
          'symbol': '2330',
          'stock_name': '台積電',
          'shares': '10',
          'price': '100',
          'currency': 'TWD',
          'net_cash_flow': '-1000'
        }
      ],
      '/api/v1/me/journal/monthly-summary?year=$year': {
        'items': [
          {
            'month': 10,
            'currency': 'TWD',
            'purchase_outflow': '1000',
            'sale_proceeds': '600',
            'cash_dividends': '50',
            'realized_pnl': '150',
            'transaction_count': 3,
            'valuation_date': '2026-10-06'
          }
        ]
      },
      '/api/v1/me/journal/symbol-summary?year=$year': {
        'items': [
          {
            'symbol': '2330',
            'stock_name': '台積電',
            'currency': 'TWD',
            'purchase_outflow': '1000',
            'sale_proceeds': '600',
            'cash_dividends': '50',
            'realized_pnl': '150',
            'transaction_count': 3,
            'valuation_date': '2026-10-06'
          }
        ]
      },
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
      '/api/v1/me/portfolio/quotes': {
        'positions': const [],
        'items': const [],
        'checked_at': '2026-10-06T14:00:00+08:00',
        'market_open': false,
      },
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FinalLedgerPage(
            api,
            now: () => DateTime.utc(2026, 10, 1, 6),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('紀錄'));
    await tester.pumpAndSettle();

    expect(find.text('年度已實現損益 TWD 150'), findsOneWidget);
    expect(find.text('按月份'), findsOneWidget);
    expect(find.text('按個股'), findsOneWidget);
    expect(find.text('2026 年 10 月'), findsOneWidget);
    expect(find.text('已實現損益 TWD 150'), findsOneWidget);
    expect(find.textContaining('買進 · 台積電（2330）'), findsNothing);

    await tester.tap(find.text('2026 年 10 月'));
    await tester.pumpAndSettle();
    expect(find.textContaining('買進 · 台積電（2330）'), findsOneWidget);

    await tester.tap(find.text('按個股'));
    await tester.pumpAndSettle();

    expect(find.text('台積電（2330）'), findsOneWidget);
    expect(find.text('已實現損益 TWD 150'), findsOneWidget);
    expect(find.text('買進支出 TWD 1,000'), findsNothing);
    expect(find.text('交易 3 筆'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Final Ledger restores manual MIS refresh on holdings',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {'items': const []},
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/journal/symbol-summary?year=$year': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
      '/api/v1/me/portfolio/quotes': {
        'positions': [
          {
            'symbol': '2330',
            'stock_name': '台積電',
            'currency': 'TWD',
            'shares': '1',
            'average_cost': '100',
            'market_price': '101.35',
            'market_value': '101.35',
            'unrealized_pnl': '1.35',
            'unrealized_return': '0.0135',
            'quote_at': '2026-10-06T13:30:00+08:00',
            'valuation_date': '2026-10-05',
            'price_status': 'available',
            'valuation_kind': 'intraday'
          }
        ],
        'items': [
          {
            'currency': 'TWD',
            'market_value': '101.35',
            'unrealized_pnl': '1.35',
            'unrealized_return': '0.0135',
            'aggregate_status': 'available',
            'valuation_date': '2026-10-05'
          }
        ],
        'checked_at': '2026-10-06T14:00:00+08:00',
        'market_open': false,
      },
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FinalLedgerPage(
            api,
            now: () => DateTime.utc(2026, 10, 1, 6),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('更新持股股價'), findsOneWidget);
    expect(find.textContaining('正式／休市'), findsOneWidget);
    expect(
      api.reads.where((path) => path == '/api/v1/me/portfolio/quotes').length,
      1,
    );

    await tester.tap(find.text('更新持股股價'));
    await tester.pumpAndSettle();

    expect(
      api.posts.where((path) => path == '/api/v1/me/portfolio/quotes/refresh').length,
      1,
    );
    expect(find.textContaining('現價 101.35 · 均價 100.00'), findsOneWidget);
    expect(find.byKey(const Key('holding-pnl-2330')), findsOneWidget);
    expect(find.byKey(const Key('holding-return-2330')), findsOneWidget);
    final holdingPnl =
        tester.widget<Text>(find.byKey(const Key('holding-pnl-2330')));
    final holdingReturn =
        tester.widget<Text>(find.byKey(const Key('holding-return-2330')));
    expect(holdingPnl.style?.color, fvGain);
    expect(holdingReturn.style?.color, fvGain);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger after 14:30 reads latest price once across tab re-entry',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {'items': const []},
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/portfolio/quotes': {
        'positions': const [],
        'items': const [],
        'checked_at': '2026-10-06T15:00:00+08:00',
        'market_open': false,
        'session': 'closed',
      },
    });
    var active = true;
    late StateSetter updateHost;

    await tester.pumpWidget(MaterialApp(
      home: StatefulBuilder(builder: (context, setState) {
        updateHost = setState;
        return FinalLedgerPage(
          api,
          active: active,
          now: () => DateTime.utc(2026, 10, 6, 7),
        );
      }),
    ));
    await tester.pumpAndSettle();
    expect(
      api.reads.where((path) => path == '/api/v1/me/portfolio/quotes').length,
      1,
    );

    updateHost(() => active = false);
    await tester.pump();
    updateHost(() => active = true);
    await tester.pumpAndSettle();

    expect(
      api.reads.where((path) => path == '/api/v1/me/portfolio/quotes').length,
      1,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger year selector reveals cleared 2025 KGI fund trades by stock',
      (tester) async {
    mobileView(tester);
    final currentYear = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {'items': const []},
      '/api/v1/me/journal/pnl?year=$currentYear': const [],
      '/api/v1/me/journal/history?year=$currentYear': const [],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/monthly-summary?year=$currentYear': {'items': const []},
      '/api/v1/me/journal/symbol-summary?year=$currentYear': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$currentYear': {'items': const []},
      '/api/v1/me/notes': const [],
      '/api/v1/me/journal/history?year=2025': [
        {
          'event_id': 'kgi-buy-1',
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'trade_date': '2025-09-11',
          'symbol': '2883',
          'stock_name': '凱基金',
          'shares': '20000',
          'price': '15.05',
          'currency': 'TWD',
          'net_cash_flow': '-301171'
        },
        {
          'event_id': 'kgi-buy-2',
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'BUY',
          'trade_date': '2025-09-24',
          'symbol': '2883',
          'stock_name': '凱基金',
          'shares': '30000',
          'price': '15.05',
          'currency': 'TWD',
          'net_cash_flow': '-451757'
        },
        {
          'event_id': 'kgi-sell',
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'SELL',
          'trade_date': '2025-10-22',
          'symbol': '2883',
          'stock_name': '凱基金',
          'shares': '50000',
          'price': '16.1',
          'currency': 'TWD',
          'net_cash_flow': '802127'
        }
      ],
      '/api/v1/me/journal/monthly-summary?year=2025': {
        'items': [
          {
            'month': 9,
            'currency': 'TWD',
            'purchase_outflow': '752928',
            'sale_proceeds': '0',
            'cash_dividends': '0',
            'realized_pnl': '0',
            'transaction_count': 2,
            'valuation_date': '2026-10-06'
          },
          {
            'month': 10,
            'currency': 'TWD',
            'purchase_outflow': '0',
            'sale_proceeds': '802127',
            'cash_dividends': '0',
            'realized_pnl': '49199',
            'transaction_count': 1,
            'valuation_date': '2026-10-06'
          }
        ]
      },
      '/api/v1/me/journal/symbol-summary?year=2025': {
        'items': [
          {
            'symbol': '2883',
            'stock_name': '凱基金',
            'currency': 'TWD',
            'purchase_outflow': '752928',
            'sale_proceeds': '802127',
            'cash_dividends': '0',
            'realized_pnl': '49199',
            'transaction_count': 3,
            'valuation_date': '2026-10-06'
          }
        ]
      },
      '/api/v1/me/journal/pnl?year=2025': [
        {
          'currency': 'TWD',
          'realized_pnl': '49199',
          'valuation_date': '2026-10-06'
        }
      ],
      '/api/v1/me/portfolio/performance?year=2025': {'items': const []},
      '/api/v1/me/portfolio/quotes': {
        'positions': const [],
        'items': const [],
        'checked_at': '2026-10-06T14:00:00+08:00',
        'market_open': false,
      },
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FinalLedgerPage(
            api,
            now: () => DateTime.utc(2026, 10, 1, 6),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('紀錄'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('年度：$currentYear'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('2025 年').last);
    await tester.pumpAndSettle();

    expect(
      api.reads,
      contains('/api/v1/me/journal/symbol-summary?year=2025'),
    );
    expect(find.text('2025 年 10 月'), findsOneWidget);

    await tester.tap(find.text('按個股'));
    await tester.pumpAndSettle();

    expect(find.text('年度已實現損益 TWD 49,199'), findsOneWidget);
    expect(find.text('凱基金（2883）'), findsOneWidget);
    expect(find.text('已實現損益 TWD 49,199'), findsOneWidget);
    expect(find.text('交易 3 筆'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Ledger Reports visualizes canonical monthly realized PnL',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {
        'items': [
          {
            'currency': 'TWD',
            'market_value': '300',
            'cost_basis': '250',
            'unrealized_pnl': '50',
            'unrealized_return': '0.2',
            'aggregate_status': 'available',
            'valuation_status': 'available',
            'ledger_version': 3,
            'valuation_date': '2026-10-05'
          }
        ]
      },
      '/api/v1/me/journal/pnl?year=$year': [
        {
          'currency': 'TWD',
          'realized_pnl': '80',
          'valuation_date': '2026-10-05'
        }
      ],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': [
        {
          'event_id': 'event-2',
          'record_version': 1,
          'event_action': 'ORIGINAL',
          'event_type': 'SELL',
          'trade_date': '2026-10-01',
          'symbol': '2330',
          'currency': 'TWD'
        }
      ],
      '/api/v1/me/journal/monthly-summary?year=$year': {
        'items': [
          {'month': 9, 'realized_pnl': '100', 'valuation_date': '2026-09-30'},
          {'month': 10, 'realized_pnl': '-20', 'valuation_date': '2026-10-05'}
        ]
      },
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
    });

    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: FinalLedgerPage(api, now: () => DateTime.utc(2026, 10, 1, 6)))),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('報表'));
    await tester.pumpAndSettle();

    expect(find.text('月度已實現損益'), findsOneWidget);
    expect(find.byKey(const Key('fv-monthly-pnl-chart')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Stock Detail keeps primary sections before lazy advanced Kline',
      (tester) async {
    mobileView(tester);
    final api = FinalFakeApi({
      '/api/v1/public/stock-health/2330': {
        'analysis_as_of': '2026-10-02',
        'data_status': 'available',
        'data': {
          'stock_name': '台積電',
          'mart_health_score': 82,
          'summary': '正式摘要',
          'supports': ['基本面可用'],
          'risks': ['估值風險'],
          'dimensions': {'fundamental': 80, 'valuation': 70},
        }
      },
      '/api/v1/public/stock-header/2330': {
        'stock_name': '台積電',
        'close': '125',
        'trade_date': '2026-10-03',
        'previous_close': '120',
        'change': '5',
        'change_percent': '0.0416666667',
      },
      '/api/v1/me/journal/positions': [
        {
          'symbol': '2330',
          'shares': '2',
          'average_cost': '100',
          'market_price': '120',
          'unrealized_pnl': '40',
          'unrealized_return': '0.2',
          'valuation_date': '2026-10-02',
          'price_date': '2026-10-02'
        }
      ],
      '/api/v1/me/portfolio/quotes': {
        'positions': [
          {
            'symbol': '2330',
            'shares': '2',
            'average_cost': '100',
            'market_price': '125',
            'unrealized_pnl': '50',
            'unrealized_return': '0.25',
            'valuation_date': '2026-10-03',
            'price_date': '2026-10-03',
            'price_status': 'available'
          }
        ],
        'items': const [],
        'market_open': false
      },
      '/api/v1/me/notes?symbol=2330': [
        {'body': '追蹤先進製程', 'needs_follow_up': true}
      ],
      '/api/v1/public/events/2330': [
        {'title': '法說會', 'event_date': '2026-10-10'}
      ],
      '/api/v1/public/kline/2330': [
        {
          'trade_date': '2026-10-02',
          'open': '100',
          'high': '121',
          'low': '99',
          'close': '120',
          'volume_shares': 100000
        },
        {
          'trade_date': '2026-10-03',
          'open': '120',
          'high': '123',
          'low': '116',
          'close': '118',
          'volume_shares': 120000
        }
      ],
    });

    await tester.pumpWidget(
      MaterialApp(home: FinalStockDetailPage(api: api, symbol: '2330')),
    );
    await tester.pumpAndSettle();

    expect(find.text('我的持股'), findsOneWidget);
    expect(find.text('正式收盤價 125.00 · 行情日 2026-10-03'), findsOneWidget);
    expect(find.text('▲ +5.00 (+4.17%)'), findsOneWidget);
    expect(find.textContaining('平均成本 100.00 · 現價 125.00'), findsOneWidget);
    expect(find.text('未實現損益 50 · 25%'), findsOneWidget);
    final priceChange = tester.widget<Text>(find.byKey(const Key('stock-price-change')));
    final unrealized = tester.widget<Text>(find.byKey(const Key('stock-unrealized-pnl')));
    expect(priceChange.style?.color, fvGain);
    expect(unrealized.style?.color, fvGain);
    expect(
      api.reads.where((path) => path == '/api/v1/public/kline/2330'),
      isEmpty,
    );

    await tester.scrollUntilVisible(
      find.byKey(const Key('fv-health-bars')),
      180,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.byKey(const Key('fv-health-bars')), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('進階資料'),
      250,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.ensureVisible(find.text('進階資料'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('進階資料'));
    await tester.pumpAndSettle();

    expect(
      api.reads.where((path) => path == '/api/v1/public/kline/2330').length,
      1,
    );
    expect(find.text('K 線／OHLCV'), findsOneWidget);
    expect(find.byKey(const Key('fv-kline-chart')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('Ledger initial holdings defers inactive section requests',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = FinalFakeApi({
      '/api/v1/me/portfolio/summary': {'items': const []},
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/positions': const [],
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/portfolio/quotes': {
        'positions': const [],
        'items': const [],
        'checked_at': '2026-10-06T14:00:00+08:00',
        'market_open': false,
      },
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FinalLedgerPage(
            api,
            now: () => DateTime.utc(2026, 10, 1, 6),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('更新持股股價'), findsOneWidget);
    expect(
      api.reads,
      isNot(contains('/api/v1/me/journal/monthly-summary?year=$year')),
    );
    expect(
      api.reads,
      isNot(contains('/api/v1/me/journal/symbol-summary?year=$year')),
    );
    expect(
      api.reads,
      isNot(contains('/api/v1/me/portfolio/performance?year=$year')),
    );
    expect(api.reads, isNot(contains('/api/v1/me/notes')));

    await tester.tap(find.text('紀錄'));
    await tester.pumpAndSettle();

    expect(
      api.reads,
      contains('/api/v1/me/journal/monthly-summary?year=$year'),
    );
    expect(
      api.reads,
      contains('/api/v1/me/journal/symbol-summary?year=$year'),
    );
    expect(
      api.reads,
      isNot(contains('/api/v1/me/portfolio/performance?year=$year')),
    );
    expect(api.reads, isNot(contains('/api/v1/me/notes')));

    await tester.tap(find.text('筆記'));
    await tester.pumpAndSettle();

    expect(api.reads, contains('/api/v1/me/notes'));
    expect(tester.takeException(), isNull);
  });

  testWidgets('holdings paints before slow history, shows official daily move, and hides four metrics off holdings',
      (tester) async {
    mobileView(tester);
    final year = DateTime.now().year;
    final api = DeferredLedgerApi({
      '/api/v1/me/portfolio/summary': {
        'items': [{
          'currency': 'TWD', 'market_value': '1622500',
          'unrealized_pnl': '-65000', 'unrealized_return': '-0.0385',
          'aggregate_status': 'available', 'valuation_date': '2026-10-08',
        }]
      },
      '/api/v1/me/journal/positions': [{
        'symbol': '2382', 'stock_name': '廣達', 'shares': '5000',
        'currency': 'TWD', 'average_cost': '337.5', 'market_price': '324.5',
        'unrealized_pnl': '-65000', 'unrealized_return': '-0.0385',
        'price_status': 'available',
      }],
      '/api/v1/me/journal/pnl?year=$year': const [],
      '/api/v1/me/journal/recalculation-status': {'status': 'IDLE'},
      '/api/v1/me/portfolio/quotes': {
        'positions': [{
          'symbol': '2382', 'stock_name': '廣達', 'shares': '5000',
          'currency': 'TWD', 'average_cost': '337.5',
          'market_price': '324.5', 'unrealized_pnl': '-65000',
          'unrealized_return': '-0.0385', 'price_status': 'available',
          'change': '-10.5', 'change_percent': '-0.03134328358',
          'day_change_amount': '-52500', 'previous_close': '335',
          'previous_close_date': '2026-10-07',
          'price_date': '2026-10-08', 'price_source': 'core_ohlcv',
        }],
        'items': [{
          'currency': 'TWD', 'market_value': '1622500',
          'unrealized_pnl': '-65000', 'unrealized_return': '-0.0385',
          'aggregate_status': 'available', 'valuation_date': '2026-10-08',
        }],
        'checked_at': '2026-10-08T14:40:00+08:00',
        'market_open': false, 'session': 'closed',
      },
    });
    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(
        api, now: () => DateTime.utc(2026, 10, 8, 7))));
    await tester.pumpAndSettle();
    expect(api.history.isCompleted, false);
    final day = tester.widget<Text>(find.byKey(const Key('holding-day-amount-2382')));
    expect(day.data, '-52,500');
    final price = tester.widget<Text>(find.byKey(const Key('holding-latest-price-2382')));
    expect(price.style?.color, fvLoss);
    expect(find.text('持股市值'), findsOneWidget);
    await tester.tap(find.text('紀錄'));
    await tester.pump();
    expect(find.text('持股市值'), findsNothing);
    await tester.tap(find.text('報表'));
    await tester.pump();
    expect(find.text('持股市值'), findsNothing);
    await tester.tap(find.text('筆記'));
    await tester.pump();
    expect(find.text('持股市值'), findsNothing);
    expect(tester.takeException(), isNull);
  });

}
