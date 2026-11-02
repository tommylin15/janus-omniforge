import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/main.dart';
import 'package:janus_user_app/personal_strategy.dart';

class MockStrategyApi extends Api {
  MockStrategyApi() : super('test');
  final List<String> calls = [];
  final List<Map<String, dynamic>> bodies = [];
  Map<String, dynamic> summary = {
    'active': {
      'version_id': '00000000-0000-0000-0000-000000000001',
      'created_at': '2026-10-31T08:00:00+08:00',
      'paused': false,
      'markdown': '# 測試策略\n**粗體規則**\nhttps://example.com/source',
      'rules': {
        'template_id': 'stock',
        'template': {'name': '股市：研究／供應鏈／執行分離'},
        'b_capacity': 8,
        'risk': {
          'tolerance': 'moderate',
          'horizon': 'medium',
          'minimum_cash_ratio': 0.2,
          'max_position_ratio': 0.3,
          'max_sector_ratio': 0.5,
          'loss_budget_ratio': 0.05,
          'max_drawdown_ratio': 0.15,
          'liquidity_need': '無',
        },
      },
    },
    'requests': [],
    'strategy_locked': false,
    'next_change_at': '2026-11-02T00:00:00+08:00',
    'saturday': true,
    'enabled': true,
  };

  List<dynamic> reportItems = [
    {
      'report_id': '00000000-0000-0000-0000-000000000002',
      'created_at': '2026-10-31T08:30:00+08:00',
      'status': 'READY',
      'model': 'gemini-2.5-flash',
      'markdown': '## 1. 外盤情勢\n正常\n\n## 支持證據\n- 營收創高',
    }
  ];

  @override
  Future<dynamic> get(String path) async {
    calls.add('GET $path');
    if (path == '/api/v1/me/personal-strategy') return summary;
    if (path.startsWith('/api/v1/me/personal-strategy/reports/')) return {'items': reportItems};
    if (path == '/api/v1/me/personal-strategy/templates') {
      return {
        'items': [
          {'id': 'stock', 'name': '股市：研究／供應鏈／執行分離'},
          {'id': 'value', 'name': 'Graham–Buffett 價值投資適配版'},
        ]
      };
    }
    if (path == '/api/v1/me/investment-profile') {
      return {'risk_tolerance': 'moderate', 'investment_horizon': 'medium', 'minimum_cash_ratio': 0.2};
    }
    return {};
  }

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    calls.add('POST $path ${body['report_type'] ?? ''}');
    bodies.add(body);
    if (path.endsWith('/preview')) return {'markdown': '# 預覽策略', 'rules': body, 'blocked': false, 'warnings': []};
    return {'request_id': '00000000-0000-0000-0000-000000000003', 'status': 'QUEUED'};
  }

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    calls.add('PUT $path');
    if (path == '/api/v1/me/personal-strategy/draft') { summary = {...summary, 'draft': Map<String, dynamic>.from(body)}; return {'saved': true}; }
    if (path == '/api/v1/me/personal-strategy/pause') {
      (summary['active'] as Map<String, dynamic>)['paused'] = body['paused'];
      return {'paused': body['paused']};
    }
    return body;
  }
}

class DelayedStrategyApi extends MockStrategyApi {
  final response = Completer<dynamic>();
  @override
  Future<dynamic> get(String path) {
    if (path == '/api/v1/me/personal-strategy') {
      calls.add('GET $path');
      return response.future;
    }
    return super.get(path);
  }
}

void main() {
  testWidgets('in-flight strategy read cannot restart polling in background', (tester) async {
    final api = DelayedStrategyApi();
    api.summary['requests'] = [{'kind': 'premarket', 'status': 'RUNNING'}];
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PersonalStrategyPage(api))));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    api.response.complete(api.summary);
    await tester.pump();
    await tester.pump(const Duration(seconds: 9));
    expect(api.calls.where((p) => p == 'GET /api/v1/me/personal-strategy').length, 1);
    await tester.pumpWidget(const SizedBox());
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
  });

  testWidgets('ResearchMarkdown renders headings, bold spans, and external links safely', (tester) async {
    const text = '# 主標題\n一般文字 **粗體重點**\nhttps://example.com/twse\n---';
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(child: ResearchMarkdown(text)),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('主標題'), findsOneWidget);
    expect(find.textContaining('粗體重點'), findsOneWidget);
    expect(find.text('開啟來源'), findsOneWidget);
    expect(find.byType(Divider), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('PersonalStrategyPage 390px mobile layout and dark mode', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = MockStrategyApi();
    await tester.pumpWidget(MaterialApp(
      theme: ThemeData.dark(),
      home: Scaffold(body: PersonalStrategyPage(api)),
    ));
    await tester.pumpAndSettle();

    // Verify Title and Tabs
    expect(find.text('個人策略'), findsOneWidget);
    expect(find.text('盤前'), findsOneWidget);
    expect(find.text('週六'), findsOneWidget);

    // Verify active strategy card and pause switch
    expect(find.textContaining('股市：研究／供應鏈／執行分離'), findsOneWidget);
    expect(find.text('暫停新建／加碼建議'), findsOneWidget);

    // Verify report card
    expect(find.textContaining('gemini-2.5-flash'), findsOneWidget);
    expect(find.text('複製Markdown'), findsOneWidget);

    // Switch to Saturday tab
    await tester.tap(find.text('週六'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('GET /api/v1/me/personal-strategy/reports/saturday'));
    expect(tester.takeException(), isNull);
  });

  testWidgets('PersonalStrategySettings renders 5 templates, risk form, and 390px bounded', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = MockStrategyApi();
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: PersonalStrategySettings(api)),
    ));
    await tester.pumpAndSettle();

    expect(find.text('個人策略設定'), findsOneWidget);
    expect(find.text('1. 操作策略'), findsOneWidget);
    expect(find.text('預覽策略與風險限制'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('settings validates missing liquidity and conflicting loss before API calls', (tester) async {
    final api = MockStrategyApi();
    final risk = api.summary['active']['rules']['risk'] as Map<String, dynamic>;
    risk['liquidity_need'] = '';
    risk['loss_budget_ratio'] = 0.20;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PersonalStrategySettings(api))));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('預覽策略與風險限制'));
    await tester.tap(find.text('預覽策略與風險限制'));
    await tester.pumpAndSettle();
    expect(find.text('請填寫資金需求；無需求請明確填「無」'), findsOneWidget);
    expect(find.text('單筆損失預算不得高於可承受總損失'), findsOneWidget);
    expect(api.calls.where((c) => c.startsWith('POST')), isEmpty);
    expect(tester.takeException(), isNull);
  });

  testWidgets('settings rejects nonfinite percentages and explains generation gate', (tester) async {
    final api = MockStrategyApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PersonalStrategySettings(api))));
    await tester.pumpAndSettle();
    final field = find.widgetWithText(TextFormField, '最低現金（%）');
    await tester.ensureVisible(field);
    await tester.enterText(field, 'NaN');
    await tester.ensureVisible(find.text('預覽策略與風險限制'));
    await tester.tap(find.text('預覽策略與風險限制'));
    await tester.pumpAndSettle();
    expect(find.text('請輸入 0～100 的百分比'), findsOneWidget);
    expect(find.text('請先完成欄位並預覽策略與風險限制。'), findsOneWidget);
    expect(api.calls.where((c) => c.startsWith('POST')), isEmpty);
  });

  testWidgets('valid settings preview shows percentages and edits invalidate generation', (tester) async {
    final api = MockStrategyApi();
    api.summary['active']['rules']['private_ai_consent'] = true;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PersonalStrategySettings(api))));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('預覽策略與風險限制'));
    await tester.tap(find.text('預覽策略與風險限制'));
    await tester.pumpAndSettle();
    expect(find.text('最低現金：20.00%'), findsOneWidget);
    expect(api.bodies.single['risk']['minimum_cash_ratio'], 0.2);
    final generate = find.widgetWithText(FilledButton, '產出個人策略並生效（每週一次）');
    expect(tester.widget<FilledButton>(generate).onPressed, isNotNull);
    final field = find.widgetWithText(TextFormField, '單股上限（%）');
    await tester.ensureVisible(field);
    await tester.enterText(field, '40');
    await tester.pump();
    expect(tester.widget<FilledButton>(generate).onPressed, isNull);
    expect(find.text('最低現金：20.00%'), findsNothing);
  });

  testWidgets('queued strategy blocks duplicate generation with a useful message', (tester) async {
    final api = MockStrategyApi();
    api.summary['requests'] = [{'kind': 'strategy', 'status': 'QUEUED'}];
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PersonalStrategySettings(api))));
    await tester.pumpAndSettle();
    expect(find.text('策略正在產出；請至個人策略頁查看進度或重試原請求。'), findsOneWidget);
    final field = find.widgetWithText(TextFormField, '資金需求／不可動用資金（必填）');
    await tester.ensureVisible(field);
    await tester.enterText(field, '保留草稿');
    api.summary = {...api.summary, 'requests': []};
    await tester.ensureVisible(find.text('更新產出狀態（保留目前填寫內容）'));
    await tester.tap(find.text('更新產出狀態（保留目前填寫內容）'));
    await tester.pumpAndSettle();
    expect(find.text('策略正在產出；請至個人策略頁查看進度或重試原請求。'), findsNothing);
    expect(find.text('保留草稿'), findsOneWidget);
    expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, '產出個人策略並生效（每週一次）')).onPressed, isNull);
  });

  testWidgets('saved incomplete strategy draft survives widget recreation without generation', (tester) async {
    final api = MockStrategyApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PersonalStrategySettings(api))));
    await tester.pumpAndSettle();
    final loss = find.widgetWithText(TextFormField, '單筆損失預算（%）');
    await tester.ensureVisible(loss);
    await tester.enterText(loss, '20');
    final liquidity = find.widgetWithText(TextFormField, '資金需求／不可動用資金（必填）');
    await tester.ensureVisible(liquidity);
    await tester.enterText(liquidity, '');
    await tester.ensureVisible(find.text('儲存設定草稿（不產出策略）'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('儲存設定草稿（不產出策略）'));
    await tester.pumpAndSettle();
    expect(find.text('設定草稿已儲存；重新登入會自動帶回。尚未變更生效策略。'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PersonalStrategySettings(api))));
    await tester.pumpAndSettle();
    expect(tester.widget<TextFormField>(loss).controller!.text, '20');
    expect(tester.widget<TextFormField>(liquidity).controller!.text, '');
    expect(api.calls.where((c) => c.startsWith('POST')), isEmpty);
    expect(api.summary['active']['rules']['risk']['loss_budget_ratio'], 0.05);
  });

}
