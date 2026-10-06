import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_pages.dart';
import 'package:janus_user_app/main.dart' as legacy;

class FinalFakeApi extends legacy.Api {
  FinalFakeApi(this.values) : super('test');

  final Map<String, dynamic> values;
  final reads = <String>[];

  @override
  Future<dynamic> get(String path) async {
    reads.add(path);
    final value = values[path];
    if (value is Exception) throw value;
    return value ?? const [];
  }

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async => body;

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async => body;

  @override
  Future<dynamic> patch(String path, Map<String, dynamic> body) async => body;
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
            'data': {'foreign': '225187325'}
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
    expect(tester.takeException(), isNull);
  });

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
      '/api/v1/me/journal/history?year=$year': const [],
      '/api/v1/me/journal/monthly-summary?year=$year': {'items': const []},
      '/api/v1/me/portfolio/performance?year=$year': {'items': const []},
      '/api/v1/me/notes': const [],
    });

    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(api)));
    await tester.pumpAndSettle();

    expect(find.text('記帳／筆記'), findsOneWidget);
    expect(find.text('持股市值'), findsOneWidget);
    expect(find.text('本年已實現損益'), findsOneWidget);
    expect(find.text('待更新／尚未確認'), findsOneWidget);
    expect(find.text('總額暫不發布'), findsWidgets);
    expect(find.text('持股'), findsWidgets);
    expect(find.text('紀錄'), findsOneWidget);
    expect(find.text('報表'), findsOneWidget);
    expect(tester.takeException(), isNull);
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

    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(api)));
    await tester.pumpAndSettle();

    expect(find.text('本年已實現損益'), findsOneWidget);
    expect(find.text('本年度確認無交易'), findsOneWidget);
    expect(find.text('待更新／尚未確認'), findsNothing);

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

    await tester.pumpWidget(MaterialApp(home: FinalLedgerPage(api)));
    await tester.pumpAndSettle();

    expect(find.text('年度損益目前無法確認'), findsOneWidget);
    expect(find.text('本年度確認無交易'), findsNothing);

    await tester.tap(find.text('報表'));
    await tester.pumpAndSettle();
    expect(find.text('本年已實現損益目前無法確認'), findsOneWidget);
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
          'close': '120'
        }
      ],
    });

    await tester.pumpWidget(
      MaterialApp(home: FinalStockDetailPage(api: api, symbol: '2330')),
    );
    await tester.pumpAndSettle();

    expect(find.text('我的持股'), findsOneWidget);
    expect(
      api.reads.where((path) => path == '/api/v1/public/kline/2330'),
      isEmpty,
    );

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
    expect(tester.takeException(), isNull);
  });
}
