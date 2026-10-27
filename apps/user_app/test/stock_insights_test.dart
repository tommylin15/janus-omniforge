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

  test('event guidance is a reading prompt, not invented company news', () {
    expect(stockEventReadingTip({'title': '現金股利公告'}), contains('配息不等於額外獲利'));
    expect(stockEventReadingTip({'title': '月營收'}), contains('比較基期'));
    expect(stockEventReadingTip({'title': '法說會'}), contains('公司展望'));
    expect(stockEventReadingTip({}), contains('不代表利多或利空'));
  });
}
