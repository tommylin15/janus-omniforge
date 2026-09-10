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
}
