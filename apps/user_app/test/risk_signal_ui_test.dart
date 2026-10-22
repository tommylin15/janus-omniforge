import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/risk_signal_ui.dart';

Map<String, dynamic> specialist({
  String modelStatus = 'oos_validated',
  String modelVersion = 'risk-xgboost8-2025h2-v1',
  double? forecast = .36,
  double? recent = .25,
}) => {
  'role': 'risk',
  'analysis_as_of': '2026-10-21',
  'model_version': modelVersion,
  'model_status': modelStatus,
  'baseline_status': 'available',
  'metrics': {
    'future_20d_volatility_annualized': forecast,
    'recent_20d_volatility_annualized': recent,
  },
};

Future<void> mount(WidgetTester tester, Map<String, dynamic> data,
    {String freshness = 'current'}) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: RiskSignalCard(specialist: data, freshness: freshness)),
  ));
}

void main() {
  testWidgets('unverified model cannot show forecast or risk direction', (tester) async {
    await mount(tester, specialist(modelStatus: 'oos_not_validated'));
    expect(find.text('模型尚待驗證'), findsOneWidget);
    expect(find.textContaining('預測 36.0%'), findsNothing);
    expect(find.textContaining('更新頻率：交易日盤後'), findsOneWidget);
  });

  testWidgets('increasing risk is an orange warning, not a price buy call', (tester) async {
    await mount(tester, specialist());
    expect(find.text('波動風險升高'), findsOneWidget);
    expect(find.textContaining('預測 36.0%'), findsOneWidget);
    expect(find.textContaining('2026/10/21'), findsNothing);
    expect(find.textContaining('資料日 2026-10-21'), findsOneWidget);
    expect(find.textContaining('買進'), findsNothing);
  });

  testWidgets('easing volatility is not a bullish or buy signal', (tester) async {
    await mount(tester, specialist(forecast: .15));
    expect(find.text('波動風險相對緩和'), findsOneWidget);
    expect(find.textContaining('低波動不代表股價將上漲'), findsOneWidget);
  });

  testWidgets('first-release approved XGB shows real risk forecast and OOS caveat', (tester) async {
    await mount(tester, specialist(modelStatus: 'first_release_approved'));
    expect(find.text('波動風險升高'), findsOneWidget);
    expect(find.textContaining('預測 36.0%'), findsOneWidget);
    expect(find.textContaining('前瞻 20 交易日樣本持續回收'), findsOneWidget);
  });

  testWidgets('expired forecast is neutral despite model numbers', (tester) async {
    await mount(tester, specialist(), freshness: 'stale');
    expect(find.text('資料已過期'), findsOneWidget);
    expect(find.textContaining('預測 36.0%'), findsNothing);
  });
}
