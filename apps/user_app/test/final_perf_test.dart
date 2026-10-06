import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_perf.dart';

void main() {
  setUp(FinalPerf.resetForTest);

  test('performance probe calculates bounded p95 samples', () {
    FinalPerf.recordCore('today', const Duration(milliseconds: 100));
    FinalPerf.recordCore('watchlist', const Duration(milliseconds: 400));
    FinalPerf.recordCore('ledger', const Duration(milliseconds: 2000));
    FinalPerf.recordCore('stock-detail', const Duration(milliseconds: 2500));
    FinalPerf.recordRestore(const Duration(milliseconds: 12));
    FinalPerf.recordRestore(const Duration(milliseconds: 280));
    FinalPerf.recordRestore(const Duration(milliseconds: 320));

    expect(FinalPerf.coreSamples, 4);
    expect(FinalPerf.coreP95, 2500);
    expect(FinalPerf.restoreSamples, 3);
    expect(FinalPerf.restoreP95, 320);
    expect(FinalPerf.latestCoreMs['ledger'], 2000);
  });

  testWidgets('performance badge reports targets without private data',
      (tester) async {
    FinalPerf.recordCore('today', const Duration(milliseconds: 900));
    FinalPerf.recordRestore(const Duration(milliseconds: 20));

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: FinalPerfBadge(alwaysShow: true),
        ),
      ),
    );

    expect(find.byKey(const Key('final-perf-badge')), findsOneWidget);
    expect(find.textContaining('core p95 900ms / ≤2000ms'), findsOneWidget);
    expect(find.textContaining('restore p95 20ms / ≤300ms'), findsOneWidget);
    expect(find.textContaining('今日 900ms'), findsOneWidget);
    expect(find.textContaining('2330'), findsNothing);
  });
}
