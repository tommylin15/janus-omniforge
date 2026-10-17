import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_common.dart';
import 'package:janus_user_app/final_visual_series.dart';

void main() {
  test('dated rows sort a copy, keep unknown dates last and bound recent history', () {
    final rows = [
      {'date': '2026-01-01'}, {'date': '2023-01-01'},
      {'date': '2026-10-16'}, {'date': null},
    ];
    final sorted = fvNewestRows(rows, fields: ['date'], now: DateTime(2026, 10, 17));
    expect(sorted.map((row) => row['date']), ['2026-10-16', '2026-01-01', null]);
    expect(rows.first['date'], '2026-01-01');
    expect(fvNewestRows(rows, fields: ['date'], recentOnly: false).length, 4);
    expect(fvDatedRowColor(0), isNot(fvDatedRowColor(1)));
  });

  Future<void> showTable(WidgetTester tester, List<dynamic> rows,
      {bool daily = false, FvTableSummary summary = FvTableSummary.latest}) async {
    tester.view.physicalSize = const Size(900, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(
      child: FvVisualSeriesChart(rows: rows, label: '測試序列', unit: 'times',
          dailyTable: daily, tableSummary: summary),
    ))));
    await tester.tap(find.text('圖表資料'));
    await tester.pumpAndSettle();
  }

  testWidgets('table quarters and striped rows are newest first; chart keeps full history', (tester) async {
    final year = DateTime.now().year;
    await showTable(tester, [
      {'date': '${year - 3}-01-31', 'value': 1},
      {'date': '$year-01-31', 'value': 10},
      {'date': '$year-05-31', 'value': 20},
      {'date': '$year-06-30', 'value': 30},
    ]);
    expect(find.textContaining('${year - 3}-01-31 ～'), findsOneWidget);
    expect(find.text('${year - 3} Q1'), findsNothing);
    expect(tester.getTopLeft(find.text('$year Q2')).dy,
        lessThan(tester.getTopLeft(find.text('$year Q1')).dy));
    await tester.tap(find.text('$year Q2'));
    await tester.pumpAndSettle();
    final latest = find.byKey(ValueKey('series-table-row-$year-06-30'));
    final older = find.byKey(ValueKey('series-table-row-$year-05-31'));
    expect(tester.getTopLeft(latest).dy, lessThan(tester.getTopLeft(older).dy));
    final colors = [latest, older].map((finder) => tester.widget<Material>(
        find.ancestor(of: finder, matching: find.byType(Material)).first).color).toList();
    expect(colors.first, isNot(colors.last));
    expect(tester.takeException(), isNull);
  });

  for (final summary in [FvTableSummary.sum, FvTableSummary.average]) {
    testWidgets('quarter summary $summary uses only listed values and refuses gaps', (tester) async {
      final year = DateTime.now().year;
      await showTable(tester, [
        {'date': '$year-01-31', 'value': 10},
        {'date': '$year-02-28', 'value': 20},
        {'date': '$year-03-31', 'value': 30},
        {'date': '$year-04-30', 'value': null},
        {'date': '$year-05-31', 'value': 50},
      ], summary: summary);
      expect(find.textContaining(summary == FvTableSummary.sum
          ? '表列合計 60.00' : '表列平均 20.00'), findsOneWidget);
      expect(find.text('2 期 · 含缺值，不彙總'), findsOneWidget);
      expect(find.textContaining('不代表完整季度報表'), findsOneWidget);
    });
  }

  testWidgets('daily table is capped at twenty recent observations', (tester) async {
    final year = DateTime.now().year;
    await showTable(tester, [
      for (var day = 1; day <= 30; day++)
        {'date': '$year-09-${day.toString().padLeft(2, '0')}', 'value': day},
    ], daily: true);
    expect(find.text('最新在上 · 最近20期日資料'), findsOneWidget);
    expect(find.text('20 期 · 最新 30.00 倍'), findsOneWidget);
    await tester.tap(find.text('$year Q3'));
    await tester.pumpAndSettle();
    expect(find.byKey(ValueKey('series-table-row-$year-09-11')), findsOneWidget);
    expect(find.byKey(ValueKey('series-table-row-$year-09-10')), findsNothing);
  });
}
