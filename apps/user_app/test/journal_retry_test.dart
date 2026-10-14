import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:janus_user_app/main.dart';

void main() {
  test('unknown journal response reuses the key after preview version changes', () async {
    final api = Api('test');
    final keys = <String>[];
    var calls = 0;
    final client = MockClient((request) async {
      keys.add(request.headers['Idempotency-Key']!);
      if (calls++ == 0) throw http.ClientException('connection lost after commit');
      return http.Response('{"event_id":"same-saved-event"}', 200);
    });
    await http.runWithClient(() async {
      const path = '/api/v1/me/journal/events';
      final trade = {'symbol': '6488', 'shares': '100', 'expected_ledger_version': 1};
      await expectLater(api.post(path, trade), throwsA(isA<http.ClientException>()));
      await api.post(path, {...trade, 'expected_ledger_version': 2});
      await api.post(path, {...trade, 'expected_ledger_version': 3});
    }, () => client);
    expect(keys[1], keys[0]);
    expect(keys[2], isNot(keys[0]));
  });
}
