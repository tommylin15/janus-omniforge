import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_visual_common.dart';

void main() {
  Map<String, dynamic> quote(String symbol, String price, {
    String basis = '374', String kind = 'EQUITY',
    String status = 'available', String state = 'intraday',
  }) => {
    'currency': 'TWD', 'symbol': symbol, 'instrument_kind': kind,
    'market_price': price, 'previous_close': basis,
    'previous_close_source': 'shioaji_previous_close',
    'price_status': status, 'quote_state': state,
  };

  test('tick-rounded exchange price, not a 10% threshold', () {
    expect(fvPriceLimitState(quote('2327', '411.00')), FvPriceLimit.up);
    expect(fvPriceLimitState(quote('2327', '337.00')), FvPriceLimit.down);
    expect(fvPriceLimitState(quote('2327', '410.50')), FvPriceLimit.none);
    expect(fvPriceLimitState(quote('2327', '411.00', status: 'stale')),
        FvPriceLimit.none);
    expect(fvPriceLimitState(quote('2327', '411.00', state: 'stale')),
        FvPriceLimit.none);
    expect(fvPriceLimitState(quote('0050', '105.05',
        basis: '95.50', kind: 'ETF')), FvPriceLimit.up);
    expect(fvPriceLimitState(quote('00697B', '105.05',
        basis: '95.50', kind: 'ETF')), FvPriceLimit.none);
    final missingRef = quote('2327', '411.00')
      ..remove('previous_close_source');
    expect(fvPriceLimitState(missingRef), FvPriceLimit.none);
  });

  testWidgets('Soft limit fills retain textual tooltips', (tester) async {
    for (final entry in [
      ('411.00', fvLimitUpFill, '漲停價'),
      ('337.00', fvLimitDownFill, '跌停價'),
    ]) {
      await tester.pumpWidget(MaterialApp(home: Scaffold(
        body: fvLimitPriceText(quote('2327', entry.$1), entry.$1,
          key: const Key('limit-price')),
      )));
      final decoration = tester.widget<Container>(
          find.byKey(const Key('limit-price'))).decoration! as BoxDecoration;
      expect(decoration.color, entry.$2);
      expect(find.byTooltip(entry.$3), findsOneWidget);
    }
  });

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
