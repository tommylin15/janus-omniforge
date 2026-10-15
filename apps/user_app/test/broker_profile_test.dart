import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/main.dart';

class BrokerApi extends Api {
  BrokerApi() : super('test');
  Map<String, dynamic> row = {'version': 0, 'declared_cash': null};
  Map<String, dynamic>? saved;
  final List<String> paths = [];
  @override
  Future<dynamic> get(String path) async { paths.add(path); return row; }
  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    paths.add(path);
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
  testWidgets('Admin edits the same owner discount through Admin auth endpoint', (tester) async {
    final api = BrokerApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: BrokerProfileCard(api, endpoint: '/api/v1/admin/broker-profile'))));
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.edit_outlined));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextFormField, '手續費折扣倍率（0～1）'), '0.4');
    await tester.tap(find.text('儲存'));
    await tester.pumpAndSettle();
    expect(api.saved!['fee_discount_multiplier'], '0.4');
    expect(api.paths, everyElement('/api/v1/admin/broker-profile'));
    expect(tester.takeException(), isNull);
  });

}
