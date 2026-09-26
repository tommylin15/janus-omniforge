import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/login_brand.dart';

void main() {
  testWidgets('login branding keeps the Janus twin-beast icon on mobile',
      (tester) async {
    expect(
      janusAppIconAsset,
      'assets/branding/janus_app_icon_512.png',
    );
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(360, 800));
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(child: buildLoginBranding(context)),
        ),
      ),
    ));
    await tester.pump();

    final image = tester.widget<Image>(find.byType(Image));
    expect((image.image as AssetImage).assetName, janusAppIconAsset);
    expect(find.text('更聰明・更安心・更愉快'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('login branding expands to the desktop hero treatment',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 800));
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(child: buildLoginBranding(context)),
        ),
      ),
    ));
    await tester.pump();

    expect(find.text('讓投資研究'), findsOneWidget);
    expect(find.text('更聰明・更安心・更愉快'), findsOneWidget);
    expect(find.textContaining('市場洞察'), findsOneWidget);
    final image = tester.widget<Image>(find.byType(Image));
    expect((image.image as AssetImage).assetName, janusAppIconAsset);
    expect(tester.takeException(), isNull);
  });

  testWidgets('desktop branding respects a narrower parent constraint',
      (tester) async {
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.binding.setSurfaceSize(const Size(1280, 800));
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: SizedBox(
              width: 760,
              child: buildLoginBranding(context),
            ),
          ),
        ),
      ),
    ));
    await tester.pump();

    expect(find.text('讓投資研究'), findsOneWidget);
    expect(find.textContaining('市場洞察'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
