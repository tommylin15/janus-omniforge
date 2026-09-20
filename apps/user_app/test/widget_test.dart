import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:janus_user_app/main.dart';

class FakeApi extends Api {
  FakeApi(this.values) : super('test');
  final Map<String, dynamic> values;
  final writes = <Map<String, dynamic>>[];
  @override
  Future<dynamic> get(String path) async => values[path] ?? const [];
  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    writes.add(body);
    return values[path] ?? body;
  }
}

void main() {
  test('private API authentication requires a Google ID token', () {
    expect(requireGoogleIdToken('id-token'), 'id-token');
    expect(() => requireGoogleIdToken(null), throwsStateError);
  });

  test('trade save wording distinguishes persistence from portfolio refresh', () {
    expect(portfolioPendingMessage, '交易已儲存，等待投資組合批次更新');
  });

  testWidgets('transaction editor shows one form and reuses the last values',
      (tester) async {
    Map<String, dynamic>? result;
    final today = DateTime.now().toIso8601String().substring(0, 10);
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => FilledButton(
                onPressed: () async {
                  result = await transactionDialog(context, initial: {
                    'event_type': 'BUY',
                    'trade_date': today,
                    'symbol': '2330',
                    'shares': '10',
                    'price': '1000'
                  });
                },
                child: const Text('開啟')))));

    await tester.tap(find.text('開啟'));
    await tester.pumpAndSettle();
    for (final label in ['交易類型', '交易日期', '股票代號', '股數', '成交單價', '幣別']) {
      expect(find.text(label), findsOneWidget);
    }
    expect(find.text('2330'), findsOneWidget);
    expect(find.text('10'), findsOneWidget);
    expect(find.text('1000'), findsOneWidget);

    await tester.enterText(find.widgetWithText(TextFormField, '股票代號'), '2317');
    await tester.tap(find.text('儲存'));
    await tester.pumpAndSettle();
    expect(result, containsPair('symbol', '2317'));
    expect(result, containsPair('shares', '10'));
    expect(result, containsPair('price', '1000'));
  });

  testWidgets('shows the Google login boundary', (tester) async {
    await tester.pumpWidget(const JanusApp());
    expect(find.text('你的私人投資工作台'), findsOneWidget);
    expect(find.text('使用 Google 登入'), findsOneWidget);
  });

  testWidgets('renders markdown code blocks without executing markup',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
            body: MarkdownText('# title\n```dart\nfinal answer = 42;\n```'))));
    expect(find.text('title'), findsOneWidget);
    expect(find.text('final answer = 42;'), findsOneWidget);
  });

  testWidgets('workspace uses five destinations and a desktop navigation rail', (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(MaterialApp(
      home: Workspace(api: FakeApi({'/api/v1/public/daily-brief': {'items': []}}),
          email: 'user@example.com', onTheme: (_) {}),
    ));
    for (final size in [const Size(360, 800), const Size(768, 1024)]) {
      await tester.binding.setSurfaceSize(size);
      await tester.pump();
      expect(find.byType(NavigationDestination), findsNWidgets(5));
      expect(tester.takeException(), isNull);
    }
    await tester.binding.setSurfaceSize(const Size(1280, 800));
    await tester.pump();
    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.text('今日'), findsNWidgets(2));
    expect(find.text('我的'), findsOneWidget);
    expect(find.byType(NavigationDestination), findsNothing);
  });

  testWidgets('blocked health cards hide the score and remain readable on a phone', (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(360, 800));
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: StockHealthCard(value: {
      'stock_id': '2330', 'data_status': 'insufficient_data', 'mart_health_score': 88,
      'ai_whitepaper_analysis': '資料仍在等待批次', 'chips_status': '中性', 'analysis_as_of': '2026-09-12',
    }))));
    expect(find.text('資料不足，暫不顯示分數'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('today marks mixed analysis dates partial and exposes screening', (tester) async {
    final api = FakeApi({'/api/v1/public/daily-brief': {'items': [{
      'analysis_as_of': '2026-09-12', 'data': {
        'component_dates': {'topics': '2026-09-11'},
        'highlights': ['重點'], 'sector_rotation': [], 'topics': [], 'candidates': []
      }
    }]}});
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: TodayPage(api))));
    await tester.pumpAndSettle();
    expect(find.textContaining('部分資料日期不一致'), findsOneWidget);
    expect(find.text('查看全市場篩選'), findsOneWidget);
  });

  testWidgets('stock detail keeps advanced market data collapsed by default', (tester) async {
    final api = FakeApi({
      '/api/v1/public/stock-health/2330': {'execution_id': '11111111-1111-1111-1111-111111111111',
        'analysis_as_of': '2026-09-12', 'scope_type': 'symbol', 'scope_id': '2330', 'data_status': 'published', 'data': {
        'stock_id': '2330', 'mart_health_score': 80, 'chips_status': '偏多',
        'ai_whitepaper_analysis': '摘要', 'analysis_as_of': '2026-09-12'
      }},
      '/api/v1/me/journal/positions': [], '/api/v1/me/notes?symbol=2330': [],
      '/api/v1/public/kline/2330': {'rows': []}, '/api/v1/public/events/2330': {'rows': []},
    });
    await tester.pumpWidget(MaterialApp(home: StockDetailPage(api: api, symbol: '2330', onAskAi: () {})));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('信心度不是獲利機率。'), findsOneWidget);
    expect(find.text('這份分析有幫助嗎？'), findsOneWidget);
    await tester.drag(find.byType(ListView), const Offset(0, -700));
    await tester.pump();
    expect(find.text('進階資料'), findsOneWidget);
    expect(find.text('K 線／OHLCV'), findsNothing);
  });

  testWidgets('analysis feedback loads the owner choice and saves a new choice', (tester) async {
    const executionId = '11111111-1111-1111-1111-111111111111';
    final feedbackPath = Uri(path: '/api/v1/me/analysis-feedback', queryParameters: {
      'analysis_execution_id': executionId, 'scope_type': 'symbol', 'scope_id': '2330',
    }).toString();
    final api = FakeApi({feedbackPath: {'feedback': 'useful'}});
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: AnalysisFeedbackCard(
        api: api, executionId: executionId, scopeType: 'symbol', scopeId: '2330'))));
    await tester.pumpAndSettle();
    expect(tester.widget<SegmentedButton<String>>(find.byType(SegmentedButton<String>)).selected,
        {'useful'});
    await tester.tap(find.text('可能誤導'));
    await tester.pumpAndSettle();
    expect(api.writes, hasLength(1));
    expect(api.writes.single, containsPair('analysis_execution_id', executionId));
    expect(api.writes.single, containsPair('feedback', 'misleading'));
  });

  testWidgets('portfolio dashboard renders persisted marts without recalculation', (tester) async {
    final api = FakeApi({
      '/api/v1/me/investment-profile': {'risk_tolerance':'moderate','investment_horizon':'long',
        'primary_goal':'growth','minimum_cash_ratio':'0.1','ai_context_opt_in':false,'version':1},
      '/api/v1/me/portfolio/summary': {'items':[{'currency':'TWD','market_value':'1200','unrealized_pnl':'200','cash_safety_status':'insufficient_data'}]},
      '/api/v1/me/portfolio/exposure': {'items':[{'industry':'semiconductor','portfolio_ratio':'1'}]},
      '/api/v1/me/portfolio/performance?year=${DateTime.now().year}': {'items':[{'year':DateTime.now().year,'currency':'TWD','xirr_status':'available','xirr':.1}]},
      '/api/v1/me/portfolio/stress-tests': {'items':[{'scenario_id':'broad_market_down_20','loss':'-240'}]},
    });
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: PortfolioDashboard(api)))));
    await tester.pumpAndSettle();
    expect(find.text('資產與風險'), findsOneWidget);
    expect(find.textContaining('市值 1200'), findsOneWidget);
    expect(find.textContaining('不構成投資建議'), findsOneWidget);
  });
}
