import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/risk_signal_ui.dart';

Map<String, dynamic> specialist({
  String status = 'ACTIVE_PREDICTED',
  double? forecast = .36,
  double? recent = .25,
}) => {
  'role': 'risk',
  'analysis_as_of': '2026-10-23',
  'model_status': 'oos_not_validated', // Historic Risk8 must never enable XGB12 display.
  'baseline_status': 'available',
  'metrics': {'recent_20d_volatility_annualized':recent},
  'seq08_native_model': {
    'status': status,
    'model_version': 'risk-xgb12-20261024',
    'input_as_of': '2026-10-23',
    'prediction': forecast,
  },
};

Future<void> mount(WidgetTester tester, Map<String, dynamic> data,
    {String freshness = 'current'}) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: RiskSignalCard(specialist: data, freshness: freshness)),
  ));
}

void main() {
  testWidgets('missing new model never substitutes the old Risk8 forecast', (tester) async {
    await mount(tester, specialist(status:'MISSING_OR_INACTIVE_ARTIFACT'));
    expect(find.text('模型尚待驗證'), findsOneWidget);
    expect(find.textContaining('預測 36.0%'), findsNothing);
    expect(find.textContaining('不顯示舊 Risk8'), findsOneWidget);
  });

  testWidgets('new Risk12 predicts higher RMS without a buy call', (tester) async {
    await mount(tester, specialist());
    expect(find.text('波動風險升高'), findsOneWidget);
    expect(find.textContaining('預測 36.0%'), findsOneWidget);
    expect(find.textContaining('2026-10-23'), findsWidgets);
    expect(find.textContaining('買進'), findsNothing);
  });

  testWidgets('lower forecast is not a bullish or trade signal', (tester) async {
    await mount(tester, specialist(forecast:.15));
    expect(find.text('波動風險相對緩和'), findsOneWidget);
    expect(find.textContaining('低波動不代表股價將上漲'), findsOneWidget);
  });

  testWidgets('new model prediction without recent volatility still displays only forecast', (tester) async {
    await mount(tester, specialist(recent:null));
    expect(find.text('風險預測可用'), findsOneWidget);
    expect(find.textContaining('年化 RMS 波動預測 36.0%'), findsOneWidget);
    expect(find.textContaining('前瞻結果仍需持續驗證'), findsOneWidget);
  });

  testWidgets('stale Risk12 cannot display forecast as current', (tester) async {
    await mount(tester, specialist(),freshness:'stale');
    expect(find.text('資料已過期'), findsOneWidget);
    expect(find.textContaining('預測 36.0%'), findsNothing);
  });
}
