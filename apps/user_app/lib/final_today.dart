import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalTodayPage extends StatefulWidget {
  const FinalTodayPage(this.api, {this.onOpenStock, super.key});

  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;

  @override
  State<FinalTodayPage> createState() => _FinalTodayPageState();
}

class _FinalTodayPageState extends State<FinalTodayPage> {
  late Future<dynamic> market = _loadMarket();
  late Future<dynamic> brief = _loadBrief();

  Future<dynamic> _loadMarket() async {
    try {
      return await widget.api.get('/api/v1/public/market-home');
    } catch (_) {
      return null;
    }
  }

  Future<dynamic> _loadBrief() async {
    try {
      return await widget.api.get('/api/v1/public/daily-brief');
    } catch (_) {
      return null;
    }
  }

  void _retryMarket() => setState(() => market = _loadMarket());
  void _retryBrief() => setState(() => brief = _loadBrief());

  String _coverage(Map<String, dynamic> section) {
    final coverage = fvMap(section['coverage']);
    final received = coverage['received_symbols'];
    final requested = coverage['requested_symbols'];
    if (received == null || requested == null) return '';
    return '涵蓋 $received/$requested 檔';
  }

  String _freshness(Map<String, dynamic> section) {
    final values = <String>[];
    if (section['as_of'] != null) values.add('資料日 ${section['as_of']}');
    final days = section['freshness_days'];
    if (days != null) values.add(days == 0 ? '最新交易日' : '$days 天前');
    final coverage = _coverage(section);
    if (coverage.isNotEmpty) values.add(coverage);
    return values.join(' · ');
  }

  String _benchmarkValue(Map<String, dynamic> section) {
    final data = fvMap(section['data']);
    final value = data['close'] ?? data['index'] ?? data['value'];
    return value == null
        ? '資料尚未取得'
        : legacy.accountingNumber(value, decimals: 2);
  }

  Widget _benchmark(String label, IconData icon, dynamic raw) {
    final section = fvMap(raw);
    final freshness = _freshness(section);
    return Expanded(
      child: SizedBox(
        height: 132,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.max,
              children: [
                Row(
                  children: [
                    Icon(icon, color: fvTeal, size: 20),
                    const SizedBox(width: 7),
                    Expanded(
                      child: Text(
                        label,
                        style: const TextStyle(
                          color: fvInk,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 9),
                Text(
                  _benchmarkValue(section),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: fvInk,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  freshness.isEmpty
                      ? legacy.uiLabel(section['status'] ?? 'partial')
                      : freshness,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: fvMuted, fontSize: 10.5),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _facts(Map<String, dynamic> section, Map<String, String> labels) {
    final data = fvMap(section['data']);
    final values = <String>[];
    for (final entry in labels.entries) {
      if (data[entry.key] != null) {
        values.add('${entry.value} ${legacy.accountingNumber(data[entry.key])}');
      }
    }
    return values.isEmpty ? '目前沒有可顯示資料' : values.join(' · ');
  }

  Widget _marketDetail(String title, IconData icon, dynamic raw,
      Map<String, String> labels) {
    final section = fvMap(raw);
    final freshness = _freshness(section);
    return fvPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: fvTeal, size: 21),
              const SizedBox(width: 9),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: fvInk,
                    fontWeight: FontWeight.w800,
                    fontSize: 16,
                  ),
                ),
              ),
              fvStatusPill(section['status'] ?? 'partial'),
            ],
          ),
          const SizedBox(height: 10),
          Text(_facts(section, labels),
              style: const TextStyle(color: fvInk, height: 1.45)),
          if (freshness.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(freshness,
                style: const TextStyle(color: fvMuted, fontSize: 11)),
          ],
        ],
      ),
    );
  }

  Widget _marketBlock() => FutureBuilder<dynamic>(
        future: market,
        builder: (context, snapshot) {
          final root = fvMap(snapshot.data);
          final sections = fvMap(root['sections']);
          final loading = snapshot.connectionState != ConnectionState.done;
          final unavailable = !loading && snapshot.data == null;
          return Column(
            children: [
              Row(
                children: [
                  _benchmark('加權指數', Icons.show_chart, sections['taiex']),
                ],
              ),
              const SizedBox(height: 10),
              if (loading)
                fvBoundedState('市場基礎資料載入中')
              else if (unavailable)
                fvPanel(
                  child: Row(
                    children: [
                      const Expanded(child: Text('市場基礎資料暫時無法使用')),
                      TextButton(onPressed: _retryMarket, child: const Text('重試')),
                    ],
                  ),
                )
              else ...[
                _marketDetail(
                  '市場活動',
                  Icons.swap_vert_circle_outlined,
                  sections['market-activity'],
                  const {
                    'day_trade_shares': '當沖股數',
                    'day_trade_buy_twd': '當沖買進',
                    'day_trade_sell_twd': '當沖賣出',
                  },
                ),
                _marketDetail(
                  '法人動向',
                  Icons.groups_2_outlined,
                  sections['institutional'],
                  const {
                    'foreign': '外資',
                    'investment_trust': '投信',
                    'dealer': '自營商',
                  },
                ),
              ],
            ],
          );
        },
      );

  Widget _briefBlock() => FutureBuilder<dynamic>(
        future: brief,
        builder: (context, snapshot) {
          final root = fvMap(snapshot.data);
          final reports = fvRows(root);
          final report = reports.isEmpty ? <String, dynamic>{} : fvMap(reports.first);
          final reportData = fvMap(report['data']);
          final data = reportData.isNotEmpty ? reportData : report;
          final highlights = fvRows(data['highlights']);
          final sectors = fvRows(data['sector_rotation']);
          final topics = fvRows(data['topics'] ?? data['hot_topics']);
          final candidates = fvRows(data['candidates']);
          final loading = snapshot.connectionState != ConnectionState.done;
          final unavailable = !loading && (snapshot.data == null || reports.isEmpty);
          final regime = data['market_regime'] ?? data['market_status'];
          final summary = data['summary'];

          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              fvSectionTitle(
                context,
                '市場判讀',
                trailing: loading
                    ? '載入中'
                    : fvText(report['analysis_as_of'], missing: '尚未就緒'),
              ),
              if (loading)
                fvBoundedState('研究內容載入中；市場基礎資料可先使用')
              else if (unavailable)
                fvPanel(
                  child: Row(
                    children: [
                      const Expanded(child: Text('研究內容尚未就緒')),
                      TextButton(onPressed: _retryBrief, child: const Text('重試')),
                    ],
                  ),
                )
              else
                fvPanel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.radar_outlined, color: fvTeal),
                          const SizedBox(width: 9),
                          Expanded(
                            child: Text(
                              legacy.uiLabel(regime ?? 'available'),
                              style: const TextStyle(
                                color: fvInk,
                                fontSize: 17,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                        ],
                      ),
                      if (summary != null) ...[
                        const SizedBox(height: 8),
                        Text('$summary',
                            style: const TextStyle(color: fvInk, height: 1.45)),
                      ],
                    ],
                  ),
                ),
              fvSectionTitle(context, '今日三件事'),
              if (highlights.isEmpty)
                fvBoundedState(loading ? '研究重點載入中' : '目前沒有可發布重點')
              else
                fvPanel(
                  child: Column(
                    children: [
                      for (var index = 0;
                          index < highlights.take(3).length;
                          index++)
                        Padding(
                          padding: EdgeInsets.only(
                            bottom: index == highlights.take(3).length - 1 ? 0 : 12,
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              CircleAvatar(
                                radius: 13,
                                backgroundColor: fvSoft,
                                child: Text(
                                  '${index + 1}',
                                  style: const TextStyle(
                                    color: fvTeal,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  fvText(
                                    highlights[index] is Map
                                        ? (fvMap(highlights[index])['title'] ??
                                            fvMap(highlights[index])['summary'])
                                        : highlights[index],
                                    missing: '重點',
                                  ),
                                  style: const TextStyle(color: fvInk, height: 1.4),
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              fvSectionTitle(context, '產業輪動／熱門話題'),
              if (sectors.isEmpty && topics.isEmpty)
                fvBoundedState(loading ? '產業與話題載入中' : '目前沒有可發布內容')
              else
                fvPanel(
                  child: Column(
                    children: [
                      for (final item in sectors.take(3))
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          dense: true,
                          leading: const Icon(Icons.trending_up, color: fvTeal),
                          title: Text(fvText(
                            item is Map
                                ? (fvMap(item)['industry'] ??
                                    fvMap(item)['name'] ??
                                    fvMap(item)['title'])
                                : item,
                          )),
                          subtitle: item is Map && fvMap(item)['state'] != null
                              ? Text(legacy.uiLabel(fvMap(item)['state']))
                              : null,
                        ),
                      for (final item in topics.take(3))
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          dense: true,
                          leading: const Icon(Icons.tag_outlined, color: fvTeal),
                          title: Text(fvText(
                            item is Map
                                ? (fvMap(item)['title'] ??
                                    fvMap(item)['topic'] ??
                                    fvMap(item)['summary'])
                                : item,
                          )),
                        ),
                    ],
                  ),
                ),
              fvSectionTitle(context, '候選股健康'),
              if (candidates.isEmpty)
                fvBoundedState(loading ? '候選股資料載入中' : '目前沒有可發布候選股')
              else
                ...candidates.take(5).map((item) {
                  final row = fvMap(item);
                  final symbol = fvText(row['stock_id'] ?? row['symbol']);
                  final score = row['mart_health_score'];
                  return fvPanel(
                    padding: EdgeInsets.zero,
                    child: ListTile(
                      onTap: symbol == '—'
                          ? null
                          : () => widget.onOpenStock?.call(symbol),
                      contentPadding:
                          const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                      title: Text(
                        fvText(row['stock_name'] ?? row['name'], missing: symbol),
                        style: const TextStyle(
                          color: fvInk,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      subtitle: Text(
                        '$symbol · ${fvText(row['analysis_as_of'] ?? report['analysis_as_of'], missing: '資料日未定')}',
                      ),
                      trailing: Text(
                        score == null
                            ? legacy.uiLabel(row['data_status'] ?? 'partial')
                            : '健康度 ${legacy.accountingNumber(score)}',
                        style: const TextStyle(
                          color: fvTeal,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  );
                }),
              fvSectionTitle(context, '全市場篩選'),
              fvBoundedState(
                data['screening'] == null && data['market_screening'] == null
                    ? '全市場篩選結果尚未就緒'
                    : fvText(data['screening'] ?? data['market_screening']),
              ),
            ],
          );
        },
      );

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: fvCanvas,
        child: SafeArea(
          bottom: false,
          child: ListView(
            key: const Key('final-today-scroll'),
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
            children: [
              fvPageTitle(
                context,
                '今日',
                subtitle: '市場基礎資料與研究內容分開載入',
              ),
              _marketBlock(),
              _briefBlock(),
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text(
                  '本服務提供研究資訊，不構成投資建議。',
                  style: TextStyle(color: fvMuted, fontSize: 12),
                ),
              ),
            ],
          ),
        ),
      );
}
