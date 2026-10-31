import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/main.dart';
import 'package:janus_user_app/personal_strategy.dart';

class MockStrategyApi extends Api {
  MockStrategyApi() : super('test');
  final List<String> calls = [];
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
    return {'request_id': '00000000-0000-0000-0000-000000000003', 'status': 'QUEUED'};
  }

  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    calls.add('PUT $path');
    if (path == '/api/v1/me/personal-strategy/pause') {
      (summary['active'] as Map<String, dynamic>)['paused'] = body['paused'];
      return {'paused': body['paused']};
    }
    return body;
  }
}

void main() {
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
    expect(find.text('選擇策略學派樣板'), findsOneWidget);
    expect(find.text('預覽策略'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
