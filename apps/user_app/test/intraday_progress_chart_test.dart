import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_series.dart';

void _mobile(WidgetTester tester) {
  tester.view.physicalSize = const Size(390, 840);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('session anchors never stretch sparse observations and show real extrema',
      (tester) async {
    _mobile(tester);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ListView(children: [
      FvIntradayProgressChart(
        label: '2330 · 已收集分鐘點', unit: '元／股', previousClose: 100,
        rows: const [
          {'date': '2026-11-05T09:03:00+08:00', 'value': '100'},
          {'date': '2026-11-05T09:04:00+08:00', 'value': '102'},
          {'date': '2026-11-05T09:05:00+08:00', 'value': '98'},
          {'date': '2026-11-05T12:00:00+08:00', 'value': '103'},
          {'date': '2026-11-05T12:01:00+08:00', 'value': '99'},
          // After close and prior-day samples must never win extrema.
          {'date': '2026-11-05T14:31:00+08:00', 'value': '500'},
          {'date': '2026-11-04T11:00:00+08:00', 'value': '300'},
        ],
      ),
    ]))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('intraday-session-fixed-chart')), findsOneWidget);
    expect(find.byKey(const Key('session-start-0900')), findsOneWidget);
    expect(find.byKey(const Key('session-end-1330')), findsOneWidget);
    expect(find.text('12:00'), findsWidgets);
    expect(find.text('09:05'), findsOneWidget);
    expect(find.text('+3.00%'), findsOneWidget);
    expect(find.text('-2.00%'), findsOneWidget);
    expect(find.textContaining('存在 1 段超過 1 分鐘的缺口'), findsOneWidget);
    expect(find.textContaining('盤中進度 67%'), findsOneWidget);
    expect(find.textContaining('前收 100.00'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('missing official previous close never invents 0-percent moves',
      (tester) async {
    _mobile(tester);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ListView(children: [
      const FvIntradayProgressChart(
        label: '沒有合法前收', unit: '點', previousClose: null,
        rows: [{'date': '2026-11-05T10:00:00+08:00', 'value': '49000'}],
      ),
    ]))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('intraday-missing-previous-close')), findsOneWidget);
    expect(find.byKey(const Key('intraday-session-fixed-chart')), findsNothing);
    expect(find.textContaining('觀測最高'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('a zero or one sample retains fixed axis without invented connecting lines',
      (tester) async {
    _mobile(tester);
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: ListView(children: [
      FvIntradayProgressChart(label: '大盤', unit: '點',
          previousClose: 20000, rows: []),
    ]))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('session-start-0900')), findsOneWidget);
    expect(find.byKey(const Key('session-end-1330')), findsOneWidget);
    expect(find.textContaining('今日尚無實際分鐘點'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('same-minute duplicate uses the later quote and is not two points',
      (tester) async {
    _mobile(tester);
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: ListView(children: [
      FvIntradayProgressChart(label: '個股', unit: '元／股',
          previousClose: 100, rows: [
            {'date': '2026-11-05T09:02:00+08:00', 'value': '99'},
            {'date': '2026-11-05T09:02:55+08:00', 'value': '101'},
          ]),
    ]))));
    await tester.pumpAndSettle();
    expect(find.textContaining('只有一個觀測點'), findsOneWidget);
    expect(find.textContaining('+1.00%'), findsWidgets);
    expect(find.textContaining('-1.00%'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
