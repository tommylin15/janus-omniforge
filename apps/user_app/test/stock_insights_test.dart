import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/stock_insights.dart';

Future<void> mount(WidgetTester tester, Widget child) async {
  await tester.pumpWidget(MaterialApp(home: Scaffold(
    body: SingleChildScrollView(child: child))));
}

void main() {
  testWidgets('bars preserve signed values, zero and nonfinite gaps', (tester) async {
    await mount(tester, const StockMetricBars({
      '上漲': 10, '下跌': -5, '持平': 0, '缺值': null, '異常': double.infinity,
    }));
    expect(find.text('上漲：+10.0%'), findsOneWidget);
    expect(find.text('下跌：-5.0%'), findsOneWidget);
    expect(find.text('持平：0.0%'), findsOneWidget);
    expect(find.text('缺值：資料不足'), findsOneWidget);
    expect(find.text('異常：資料不足'), findsOneWidget);
    final bars = tester.widgetList<FractionallySizedBox>(find.byType(FractionallySizedBox));
    expect(bars.map((bar) => bar.widthFactor), [0, 1, .5, 0, 0, 0]);
  });

  testWidgets('valuation uses actual midpoint and refuses reversed or undated bands', (tester) async {
    final reference = <String, dynamic>{'status': 'available',
      'as_of': '2026-10-27', 'lower': 100, 'mid': 125, 'upper': 200};
    await mount(tester, StockValuationBand(reference));
    expect(find.text('中位 125.00'), findsOneWidget);
    expect(tester.widgetList<Align>(find.byType(Align))
      .any((widget) => widget.alignment == const Alignment(-.5, 0)), isTrue);
    for (final invalid in [
      {...reference, 'upper': 110}, {...reference, 'as_of': null},
      {...reference, 'mid': double.nan}, {...reference, 'status': 'partial'},
    ]) {
      await mount(tester, StockValuationBand(invalid));
      expect(find.textContaining('參考價帶資料不足'), findsOneWidget);
      expect(find.text('中位 125.00'), findsNothing);
    }
  });

  testWidgets('blocked metrics cannot leak into observed charts', (tester) async {
    await mount(tester, StockFactsPanel({'freshness': 'stale', 'specialists': [
      {'role': 'quant', 'status': 'blocked', 'baseline_status': 'unavailable',
        'analysis_as_of': '2026-10-27', 'metrics': {'return_5d_percent': 99}},
    ]}));
    expect(find.text('近 5 個交易日：資料不足'), findsOneWidget);
    expect(find.textContaining('+99.0%'), findsNothing);
    expect(find.textContaining('資料過期，僅供歷史參考'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('renders all four aspects cleanly at 390px with 200% text scale without overflow', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final baseline = {
      'freshness': 'current',
      'specialists': [
        {
          'role': 'quant',
          'status': 'ACTIVE_PREDICTED',
          'baseline_status': 'available',
          'analysis_as_of': '2026-10-27',
          'metrics': {'return_5d_percent': 2.5, 'return_20d_percent': -3.2, 'return_60d_percent': 15.0},
          'plain_language': '5日報酬 +2.5%，20日報酬 -3.2%'
        },
        {
          'role': 'fundamental',
          'status': 'ACTIVE_CACHED',
          'baseline_status': 'available',
          'analysis_as_of': '2026-10-27',
          'metrics': {'revenue_trend_percent': 12.3, 'eps_trend_percent': 8.5},
          'plain_language': '營收年增 12.3%，每股盈餘成長 8.5%'
        },
        {
          'role': 'valuation',
          'status': 'ACTIVE_CACHED',
          'baseline_status': 'available',
          'analysis_as_of': '2026-10-27',
          'metrics': {'pe_ratio': 18.5, 'pb_ratio': 2.4},
          'plain_language': '本益比 18.5 倍，股價淨值比 2.4 倍'
        },
        {
          'role': 'risk',
          'status': 'ACTIVE_PREDICTED',
          'baseline_status': 'available',
          'analysis_as_of': '2026-10-27',
          'metrics': {'recent_realized_volatility': 0.22, 'predicted_volatility': 0.28},
          'plain_language': '預期未來波動 28%'
        }
      ],
      'valuation_reference': {
        'status': 'available',
        'as_of': '2026-10-27',
        'lower': 100.0,
        'mid': 125.0,
        'upper': 150.0
      },
      'four_model_serving': {
        'risk': {
          'model_version': 'risk12-20261026',
          'recent_volatility': 0.22,
          'predicted_volatility': 0.28,
          'status': 'ACTIVE_PREDICTED'
        }
      }
    };

    await tester.pumpWidget(MaterialApp(
      home: MediaQuery(
        data: const MediaQueryData(
          size: Size(390, 844),
          textScaler: TextScaler.linear(2),
        ),
        child: Scaffold(
          body: SingleChildScrollView(child: StockFactsPanel(baseline)),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('用四個角度看懂這家公司'), findsOneWidget);
    expect(find.text('股價走勢'), findsOneWidget);
    expect(find.text('公司營運'), findsOneWidget);
    expect(find.text('價格評價'), findsOneWidget);
    expect(find.textContaining('波動風險'), findsWidgets);
    expect(find.text('近 5 個交易日：+2.5%'), findsOneWidget);
    expect(find.text('中位 125.00'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test('event guidance is a reading prompt, not invented company news', () {
    expect(stockEventReadingTip({'title': '現金股利公告'}), contains('配息不等於額外獲利'));
    expect(stockEventReadingTip({'title': '月營收'}), contains('比較基期'));
    expect(stockEventReadingTip({'title': '法說會'}), contains('公司展望'));
    expect(stockEventReadingTip({}), contains('不代表利多或利空'));
  });
}
