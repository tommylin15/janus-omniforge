import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_common.dart';

void main() {
  test('Life-style pastel tones are distinct presentation-only gradients', () {
    final tones = FvCardTone.values.map((tone) {
      final decoration = fvPastelDecoration(tone: tone);
      expect(decoration.gradient, isA<LinearGradient>());
      expect(decoration.borderRadius, BorderRadius.circular(20));
      expect(decoration.border, isNotNull);
      return (decoration.gradient! as LinearGradient).colors.first;
    }).toSet();
    expect(tones.length, FvCardTone.values.length);
    expect(fvSignedColor('100'), fvGain);
    expect(fvSignedColor('-100'), fvLoss);
  });

  testWidgets('Pastel panel keeps data text and gradient on a phone',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: Scaffold(
      body: fvPanel(tone: FvCardTone.mint, child: const Text('持股市值')),
    )));
    expect(find.text('持股市值'), findsOneWidget);
    final inks = tester.widgetList<Ink>(find.byType(Ink));
    expect(inks.any((ink) => ink.decoration is BoxDecoration &&
        (ink.decoration! as BoxDecoration).gradient is LinearGradient), isTrue);
    expect(tester.takeException(), isNull);
  });
}
