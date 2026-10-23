import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_analysis.dart';
import 'package:janus_user_app/admin_analysis.dart';
import 'package:janus_user_app/main.dart';

class AnalysisApi extends Api {
  AnalysisApi({this.canRequest = false, this.active = false}) : super('test');
  final bool canRequest, active;
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
    if (path.endsWith('/ceo'))
      return {
        'items': active
            ? [
                {'request_id': 'r1', 'status': 'RUNNING'}
              ]
            : [],
        'capability': {'can_request': canRequest, 'profile_approved': true}
      };
    return {
      'analysis_as_of': '2026-10-11',
      'freshness': 'current',
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
    expect(find.text('真實基準；模型品質尚未驗證'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '分析'), findsNothing);
    expect(api.posts, isEmpty);
    expect(tester.takeException(), isNull);
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
