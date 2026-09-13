import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:janus_user_app/main.dart';

void main() {
  testWidgets('shows the Google login boundary', (tester) async {
    await tester.pumpWidget(const JanusApp());
    expect(find.text('你的私人投資工作台'), findsOneWidget);
    expect(find.text('使用 Google 登入'), findsOneWidget);
  });

  testWidgets('renders markdown code blocks without executing markup',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
            body: MarkdownText('# title\n```dart\nfinal answer = 42;\n```'))));
    expect(find.text('title'), findsOneWidget);
    expect(find.text('final answer = 42;'), findsOneWidget);
  });

  testWidgets('workspace keeps the five user destinations at phone and desktop widths', (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(MaterialApp(
      home: Workspace(api: Api('test'), email: 'user@example.com', onTheme: (_) {}),
    ));
    for (final size in [const Size(360, 800), const Size(768, 1024), const Size(1280, 800)]) {
      await tester.binding.setSurfaceSize(size);
      await tester.pump();
      expect(find.byType(NavigationDestination), findsNWidgets(5));
      expect(tester.takeException(), isNull);
    }
  });

  testWidgets('blocked health cards hide the score and remain readable on a phone', (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(360, 800));
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: StockHealthCard(value: {
      'symbol': '2330', 'status': 'insufficient_data', 'score': 88,
      'summary': '資料仍在等待批次', 'positioning': '中性', 'analysis_as_of': '2026-09-12',
    }))));
    expect(find.text('資料不足，暫不顯示分數'), findsOneWidget);
    expect(find.textContaining('健康度：'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
