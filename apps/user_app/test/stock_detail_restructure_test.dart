import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/final_stock_detail.dart';
import 'package:janus_user_app/model_timeline.dart';
import 'final_visual_test.dart' show FinalFakeApi, stockSection, stockScroll;

Map<String, dynamic> timeline() => {
      'as_of': '2026-10-22',
      'source_ids': ['twse', 'mops'],
      'roles': {
        for (final role in [
          'quant',
          'risk',
          'fundamental',
          'valuation_pe',
          'valuation_pb'
        ])
          role: {
            'observed': [
              {'date': '2026-09-01', 'value': 20},
              {'date': '2026-09-02', 'value': 24},
            ],
            'forecasts': [
              {
                'date': '2026-09-02',
                'signal_date': '2026-08-05',
                'published_date': '2026-08-05',
                'value': 30,
                'actual': 24,
                'model_version': '$role-v1',
                'evaluation_kind': 'published'
              },
              {
                'date': '2026-11-02',
                'signal_date': '2026-10-02',
                'published_date': '2026-10-03',
                'value': 36,
                'actual': null,
                'model_version': '$role-v1',
                'evaluation_kind': 'retrospective'
              },
            ],
            'pending': 1,
            'missing': 2,
          },
      },
    };

Future<void> capture(WidgetTester tester, String name) async {
  await tester.pumpAndSettle();
  final boundary = tester.renderObject<RenderRepaintBoundary>(
      find.byKey(const Key('stock-preview')));
  await tester.runAsync(() async {
    final image = await boundary.toImage(pixelRatio: 2);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    await Directory('build/stock-detail-preview').create(recursive: true);
    await File('build/stock-detail-preview/$name.png')
        .writeAsBytes(bytes!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  testWidgets(
      'all four models show task-specific histories, pending outcomes and readable enlarged text',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        home: MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(2)),
            child: Scaffold(
                body: SingleChildScrollView(
                    child: ModelTimelinePanel(timeline()))))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('model-timeline-risk')), findsOneWidget);
    expect(find.byKey(const Key('model-timeline-quant')), findsNothing);
    expect(find.textContaining('20 日期間的結束日對齊'), findsOneWidget);
    expect(find.textContaining('36% 是年化波動'), findsOneWidget);
    expect(find.textContaining('最近實際波動 24.00%'), findsNothing);
    await tester.pumpWidget(MaterialApp(home: MediaQuery(
      data: const MediaQueryData(textScaler: TextScaler.linear(2)),
      child: Scaffold(body: SingleChildScrollView(child:
          ModelTimelinePanel({...timeline(), 'as_of': '2026-09-03'}))))));
    await tester.pumpAndSettle();
    expect(find.textContaining('最近實際波動 24.00%'), findsOneWidget);
    for (final role in ['quant', 'fundamental', 'valuation', 'risk']) {
      await tester.ensureVisible(find.byKey(Key('model-role-$role')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(Key('model-role-$role')));
      await tester.pumpAndSettle();
      expect(
          find.byKey(Key(
              'model-timeline-${role == 'valuation' ? 'valuation_pe' : role}')),
          findsOneWidget);
      if (role == 'valuation') {
        expect(find.byKey(const Key('model-timeline-valuation_pb')),
            findsOneWidget);
      }
      expect(find.textContaining('事後重算對照'),
          findsNWidgets(role == 'valuation' ? 2 : 1));
      expect(find.textContaining('暫不能判斷預測效果'),
          findsNWidgets(role == 'valuation' ? 2 : 1));
      expect(tester.takeException(), isNull);
    }
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'stock sections isolate charts, cache reads, and preserve research without fetching notes or news',
      (tester) async {
    final font = File('${Platform.environment['WINDIR']}/Fonts/msjh.ttc');
    if (font.existsSync()) {
      await tester.runAsync(() async {
        await (FontLoader('Roboto')
              ..addFont(
                  Future.value(ByteData.sublistView(await font.readAsBytes()))))
            .load();
        await (FontLoader('MaterialIcons')
              ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf')))
            .load();
      });
    }
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = FinalFakeApi({
      '/api/v1/public/stock-header/2330': {
        'stock_name': '台積電',
        'close': 100,
        'instrument_kind': 'COMMON_STOCK'
      },
      '/api/v1/me/portfolio/snapshot': {'positions': []},
      '/api/v1/public/kline/2330': [
        for (var i = 1; i <= 20; i++)
          {
            'trade_date': '2026-09-${i.toString().padLeft(2, '0')}',
            'open': 100 + i,
            'high': 104 + i,
            'low': 98 + i,
            'close': 102 + i,
            'volume_shares': 100000 + i * 1000
          },
      ],
      '/api/v1/public/stocks/2330/price-series?period=week&limit=300': {
        'period': 'week',
        'source_ids': ['twse'],
        'bars': [
          for (var i = 1; i <= 3; i++)
            {
              'date': '2026-09-${(i * 7).toString().padLeft(2, '0')}',
              'open': 100,
              'high': 110,
              'low': 90,
              'close': 100 + i,
              'volume_shares': 10000
            },
        ],
      },
      '/api/v1/public/stocks/2330/visual-series?metric=revenue&limit=120': {
        'metric': 'revenue',
        'unit': 'TWD_thousands',
        'data_as_of': '2026-09-30',
        'points': [
          {'date': '2026-08-31', 'value': 100000},
          {'date': '2026-09-30', 'value': 110000},
        ],
      },
      '/api/v1/me/analysis/2330/model-timeline': timeline(),
    });
    await tester.pumpWidget(MaterialApp(
        theme: ThemeData(
            colorScheme:
                ColorScheme.fromSeed(seedColor: const Color(0xFF177F88))),
        home: RepaintBoundary(
            key: const Key('stock-preview'),
            child: FinalStockDetailPage(api: api, symbol: '2330'))));
    await tester.pumpAndSettle();
    await capture(tester, 'overview');
    expect(
        api.reads.where(
            (p) => p.contains('visual-series') || p.contains('model-timeline')),
        isEmpty);
    await stockSection(tester, 'technical');
    await tester.scrollUntilVisible(
        find.byKey(const Key('stock-period-week')), 180,
        scrollable: stockScroll);
    await tester.tap(find.byKey(const Key('stock-period-week')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('fv-period-k-chart')), findsOneWidget);
    await stockSection(tester, 'fundamentals');
    await tester.scrollUntilVisible(
        find.byKey(const Key('revenue-cumulative')), 180,
        scrollable: stockScroll);
    await tester.tap(find.byKey(const Key('revenue-cumulative')));
    await tester.pumpAndSettle();
    expect(find.textContaining('缺月不補值'), findsOneWidget);
    await stockSection(tester, 'valuation');
    expect(find.byKey(const Key('visual-tab-revenue')), findsNothing);
    await stockSection(tester, 'fundamentals');
    expect(api.reads.where((p) => p.contains('metric=revenue')).length, 1);
    await stockSection(tester, 'research');
    await tester.scrollUntilVisible(find.text('模型要回答什麼，後來發生了什麼？'), 180,
        scrollable: stockScroll);
    expect(find.byKey(const Key('model-timeline-risk')), findsOneWidget);
    await capture(tester, 'research');
    expect(
        api.reads.where((p) => p.contains('/notes?') || p.contains('/events/')),
        isEmpty);
    expect(api.posts, isEmpty);
    expect(tester.takeException(), isNull);
  });
}
