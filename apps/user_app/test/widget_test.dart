import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/main.dart';

void main() {
  testWidgets('shows the Google login boundary', (tester) async {
    await tester.pumpWidget(const JanusApp());
    expect(find.text('你的私人投資工作台'), findsOneWidget);
    expect(find.text('使用 Google 登入'), findsOneWidget);
  });
}
