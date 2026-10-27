import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_analysis.dart';
import 'package:janus_user_app/admin_analysis.dart';
import 'package:janus_user_app/main.dart';

class AnalysisApi extends Api {
  AnalysisApi({this.canRequest = false, this.active = false,
      this.ceoUnavailable = false}) : super('test');
  final bool canRequest, active, ceoUnavailable;
  final posts = <String>[];
  @override
  Future<dynamic> get(String path) async {
    if (path == '/api/v1/admin/analysis')
      return {
        'profiles': [],
        'capabilities': [],
        'executions': [],
        'specialists': []
      };
    if (path.endsWith('/reports')) return {'status': 'waiting', 'items': []};
    if (path.endsWith('/ceo')) {
      if (ceoUnavailable) throw StateError('CEO endpoint unavailable');
      return {
        'items': active
            ? [
                {'request_id': 'r1', 'status': 'RUNNING'}
              ]
            : [],
        'capability': {'can_request': canRequest, 'profile_approved': true}
      };
    }
    return {
      'analysis_as_of': '2026-10-11',
      'freshness': 'current',
      'stock_report': {
        'report_as_of': '2026-10-10', 'policy_version': 'stock-report-weekly-change-v1',
        'generation_reason': 'first_report',
        'inputs_as_of': {'quant': '2026-10-10'},
        'serving_roles': [{'role': 'quant', 'status': 'MISSING_OR_INACTIVE_ARTIFACT',
                            'model_version': null, 'prediction': null}],
        'input_gaps': {'quant': ['ret5']},
      },
      'stock_report_refresh': {'generated': false, 'checked_as_of': '2026-10-11'},
      'specialists': [
        {
          'role': 'quant',
          'baseline_status': 'available',
          'plain_language': '真實基準；模型品質尚未驗證',
          'analysis_as_of': '2026-10-11'
        }
      ]
    };
  }

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    posts.add(path);
    return {'status': 'QUEUED'};
  }
}

void main() {
  testWidgets(
      'persisted reads show baselines and never call CEO without permission',
      (tester) async {
    final api = AnalysisApi();
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: FinalAnalysisPanel(api, '2330')))));
    await tester.pumpAndSettle();
    expect(find.text('模型能回答什麼？'), findsOneWidget);
    expect(find.text('真實基準；模型品質尚未驗證'), findsNothing);
    expect(find.textContaining('報告資料日 2026-10-10'), findsOneWidget);
    expect(find.textContaining('沿用上次成功報告'), findsOneWidget);
    expect(find.textContaining('模型狀態 MISSING_OR_INACTIVE_ARTIFACT'), findsNothing);
    expect(find.textContaining('暫無可用預測'), findsNWidgets(4));
    expect(find.widgetWithText(FilledButton, '分析'), findsNothing);
    expect(api.posts, isEmpty);
    expect(tester.takeException(), isNull);
  });
  testWidgets('CEO outage preserves latest deterministic report and blocks dispatch',
      (tester) async {
    final api = AnalysisApi(ceoUnavailable: true);
    await tester.pumpWidget(MaterialApp(home: Scaffold(
      body: SingleChildScrollView(child: FinalAnalysisPanel(api, '2330')))));
    await tester.pumpAndSettle();
    expect(find.textContaining('報告資料日 2026-10-10'), findsOneWidget);
    expect(find.textContaining('事實報告仍可閱讀'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '分析'), findsNothing);
    expect(api.posts, isEmpty);
  });
  testWidgets(
      'authorized user explicitly requests analysis, active request disables duplicates',
      (tester) async {
    final api = AnalysisApi(canRequest: true);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: FinalAnalysisPanel(api, '2330')))));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.widgetWithText(FilledButton, '分析'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '分析'));
    await tester.pumpAndSettle();
    expect(api.posts, ['/api/v1/me/analysis/2330/ceo']);
    final active = AnalysisApi(canRequest: true, active: true);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: FinalAnalysisPanel(active, '2330',
                    key: const Key('active'))))));
    await tester.pump();
    await tester.pump();
    expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '重新分析'))
            .onPressed,
        isNull);
    expect(find.text('中止'), findsOneWidget);
    expect(active.posts, isEmpty);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets(
      'Admin model/report page does not enable providers without evidence',
      (tester) async {
    final api = AnalysisApi();
    await tester
        .pumpWidget(MaterialApp(home: Scaffold(body: AdminAnalysisPage(api))));
    await tester.pumpAndSettle();
    expect(find.text('模型與報告管理'), findsOneWidget);
    expect(find.textContaining('登入、品質或費用證據不足'), findsOneWidget);
    expect(api.posts, isEmpty);
  });
}
