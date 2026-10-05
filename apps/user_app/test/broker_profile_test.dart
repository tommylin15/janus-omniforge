import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/main.dart';

class BrokerApi extends Api {
  BrokerApi() : super('test');
  Map<String, dynamic> row = {'version': 0, 'declared_cash': null};
  Map<String, dynamic>? saved;
  @override
  Future<dynamic> get(String path) async => row;
  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    saved = body;
    row = {...body, 'version': 1};
    return row;
  }
}

void main() {
  testWidgets('390px profile shows missing cash and saves server version', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = BrokerApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: BrokerProfileCard(api))));
    await tester.pumpAndSettle();
    expect(find.textContaining('申報現金 未設定'), findsOneWidget);
    await tester.tap(find.byIcon(Icons.edit_outlined));
    await tester.pumpAndSettle();
    expect(find.textContaining('不代表正式現金餘額'), findsOneWidget);
    await tester.tap(find.text('儲存'));
    await tester.pumpAndSettle();
    expect(api.saved!['expected_version'], 0);
    expect(api.saved!['declared_cash'], isNull);
    expect(api.saved!['cash_as_of'], isNull);
    expect(find.textContaining('版本 1'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
